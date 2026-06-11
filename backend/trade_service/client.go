package main

import (
	"encoding/json"
	"log"
	"time"

	"github.com/gorilla/websocket"
)

const (
	writeWait      = 10 * time.Second
	pongWait       = 60 * time.Second
	pingPeriod     = (pongWait * 9) / 10
	maxMessageSize = 4096
)

type Client struct {
	hub    *Hub
	conn   *websocket.Conn
	send   chan []byte
	heroID string
}

func (c *Client) readPump() {
	defer func() {
		c.hub.unregister <- c
		c.conn.Close()
	}()

	c.conn.SetReadLimit(maxMessageSize)
	c.conn.SetReadDeadline(time.Now().Add(pongWait))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	for {
		_, message, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseNormalClosure) {
				log.Printf("read error: %v", err)
			}
			break
		}
		c.handleMessage(message)
	}
}

func (c *Client) writePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			if err := c.conn.WriteMessage(websocket.TextMessage, message); err != nil {
				return
			}
		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

func (c *Client) handleMessage(raw []byte) {
	var envelope struct {
		Type   string `json:"type"`
		ToID   string `json:"to_id,omitempty"`
		ItemID string `json:"item_id,omitempty"`
	}

	if err := json.Unmarshal(raw, &envelope); err != nil {
		return
	}

	switch envelope.Type {
	case "trade_request":
		c.handleTradeRequest(envelope.ToID)
	case "trade_accept":
		c.handleTradeAccept(envelope.ToID)
	case "trade_decline":
		c.handleTradeDecline(envelope.ToID)
	case "item_offer":
		c.handleItemOffer(envelope.ItemID)
	case "trade_confirm":
		c.handleTradeConfirm()
	case "trade_cancel":
		c.handleTradeCancel()
	}
}

func (c *Client) handleTradeRequest(targetID string) {
	target := c.hub.findClientByID(targetID)
	if target == nil {
		return
	}
	msg, _ := encode(TradeRequest{Type: "trade_request", FromID: c.heroID, ToID: targetID})
	target.send <- msg
}

func (c *Client) handleTradeAccept(targetID string) {
	target := c.hub.findClientByID(targetID)
	if target == nil {
		return
	}

	if c.hub.findTradeKey(c.heroID) != "" || c.hub.findTradeKey(targetID) != "" {
		return
	}

	key := c.heroID + ":" + targetID
	if c.heroID > targetID {
		key = targetID + ":" + c.heroID
	}

	c.hub.mu.Lock()
	c.hub.trades[key] = &TradeSession{
		PlayerA: c.heroID,
		PlayerB: targetID,
	}
	c.hub.mu.Unlock()

	msg, _ := encode(TradeAccept{Type: "trade_accept", FromID: c.heroID, ToID: targetID})
	target.send <- msg
}

func (c *Client) handleTradeDecline(targetID string) {
	target := c.hub.findClientByID(targetID)
	if target == nil {
		return
	}
	msg, _ := encode(TradeDecline{Type: "trade_decline", FromID: c.heroID, ToID: targetID})
	target.send <- msg
}

func (c *Client) handleItemOffer(itemID string) {
	partner := c.hub.findTradePartner(c.heroID)
	if partner == nil {
		return
	}

	key := c.hub.findTradeKey(c.heroID)
	if key == "" {
		return
	}

	c.hub.mu.Lock()
	if s, ok := c.hub.trades[key]; ok {
		if c.heroID == s.PlayerA {
			s.OfferA = itemID
		} else {
			s.OfferB = itemID
		}
	}
	c.hub.mu.Unlock()

	msg, _ := encode(ItemOffer{Type: "item_offer", FromID: c.heroID, ItemID: itemID})
	partner.send <- msg
}

func (c *Client) handleTradeConfirm() {
	key := c.hub.findTradeKey(c.heroID)
	if key == "" {
		return
	}

	c.hub.mu.Lock()
	s, ok := c.hub.trades[key]
	if !ok {
		c.hub.mu.Unlock()
		return
	}

	if c.heroID == s.PlayerA {
		s.ConfirmA = true
	} else {
		s.ConfirmB = true
	}

	if s.ConfirmA && s.ConfirmB {
		delete(c.hub.trades, key)
		c.hub.mu.Unlock()

		msg, _ := encode(TradeComplete{Type: "trade_complete"})
		if a := c.hub.findClientByID(s.PlayerA); a != nil {
			a.send <- msg
		}
		if b := c.hub.findClientByID(s.PlayerB); b != nil {
			b.send <- msg
		}
		return
	}
	c.hub.mu.Unlock()
}

func (c *Client) handleTradeCancel() {
	partner := c.hub.findTradePartner(c.heroID)
	if partner == nil {
		return
	}

	key := c.hub.findTradeKey(c.heroID)
	c.hub.mu.Lock()
	delete(c.hub.trades, key)
	c.hub.mu.Unlock()

	msg, _ := encode(TradeCancel{Type: "trade_cancel", FromID: c.heroID})
	partner.send <- msg
}
