package main

import (
	"encoding/json"
	"sync"
)

type TradeSession struct {
	PlayerA  string
	PlayerB  string
	OfferA   string
	OfferB   string
	ConfirmA bool
	ConfirmB bool
}

type Hub struct {
	clients    map[*Client]bool
	trades     map[string]*TradeSession
	broadcast  chan []byte
	register   chan *Client
	unregister chan *Client
	mu         sync.RWMutex
}

func NewHub() *Hub {
	return &Hub{
		clients:    make(map[*Client]bool),
		trades:     make(map[string]*TradeSession),
		broadcast:  make(chan []byte, 256),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()
			h.broadcastLobby()

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
				h.cancelTradeOnDisconnect(client)
			}
			h.mu.Unlock()
			h.broadcastLobby()

		case message := <-h.broadcast:
			h.mu.RLock()
			for client := range h.clients {
				select {
				case client.send <- message:
				default:
					close(client.send)
					delete(h.clients, client)
				}
			}
			h.mu.RUnlock()
		}
	}
}

func (h *Hub) cancelTradeOnDisconnect(client *Client) {
	key := h.findTradeKey(client.heroID)
	if key == "" {
		return
	}
	session := h.trades[key]
	var partnerID string
	if session.PlayerA == client.heroID {
		partnerID = session.PlayerB
	} else {
		partnerID = session.PlayerA
	}
	delete(h.trades, key)

	if partner := h.findClientByID(partnerID); partner != nil {
		msg, _ := encode(TradeCancel{Type: "trade_cancel", FromID: client.heroID})
		partner.send <- msg
	}
}

func (h *Hub) onlineIDs() []string {
	h.mu.RLock()
	defer h.mu.RUnlock()
	ids := make([]string, 0, len(h.clients))
	for c := range h.clients {
		ids = append(ids, c.heroID)
	}
	return ids
}

func (h *Hub) broadcastLobby() {
	ids := h.onlineIDs()
	msg, _ := encode(LobbyUpdate{Type: "lobby_update", OnlinePlayers: ids})
	h.broadcast <- msg
}

func (h *Hub) findClientByID(id string) *Client {
	for c := range h.clients {
		if c.heroID == id {
			return c
		}
	}
	return nil
}

func (h *Hub) findTradeKey(heroID string) string {
	for key, s := range h.trades {
		if s.PlayerA == heroID || s.PlayerB == heroID {
			return key
		}
	}
	return ""
}

func (h *Hub) findTradePartner(heroID string) *Client {
	key := h.findTradeKey(heroID)
	if key == "" {
		return nil
	}
	s := h.trades[key]
	partnerID := s.PlayerB
	if heroID == s.PlayerB {
		partnerID = s.PlayerA
	}
	return h.findClientByID(partnerID)
}

type RawMessage struct {
	Type   string          `json:"type"`
	ToID   string          `json:"to_id,omitempty"`
	ItemID string          `json:"item_id,omitempty"`
	Raw    json.RawMessage `json:"-"`
}
