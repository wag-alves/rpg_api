package main

import (
	"encoding/json"
	"log"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

type Client struct {
	hub       *Hub
	conn      *websocket.Conn
	send      chan []byte
	HeroID    string
	HeroName  string
	HeroClass string
	HeroATK   int
	Slot      int
	mu        sync.Mutex
	lastAttack time.Time
}

const (
	attackCooldown = 2 * time.Second
	writeWait      = 10 * time.Second
	pongWait       = 60 * time.Second
	pingPeriod     = (pongWait * 9) / 10
	maxMessageSize = 256
)

func NewClient(hub *Hub, conn *websocket.Conn) *Client {
	return &Client{
		hub:  hub,
		conn: conn,
		send: make(chan []byte, 256),
	}
}

func (c *Client) ReadPump() {
	defer func() {
		c.hub.Unregister <- c
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
			break
		}

		var msg ClientMessage
		if err := json.Unmarshal(message, &msg); err != nil {
			continue
		}

		switch msg.Type {
		case "attack":
			c.handleAttack()
		}
	}
}

func (c *Client) WritePump() {
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

func (c *Client) handleAttack() {
	c.mu.Lock()
	elapsed := time.Since(c.lastAttack)
	if elapsed < attackCooldown {
		c.mu.Unlock()
		return
	}
	c.lastAttack = time.Now()
	c.mu.Unlock()

	if !c.hub.boss.IsActive() {
		c.sendJSON(ServerMessage{
			Type: "error",
			Payload: map[string]string{
				"message": "Nenhum boss ativo no momento!",
			},
		})
		return
	}

	damage := c.hub.boss.TakeDamage(c.HeroName, c.HeroATK)
	if damage > 0 {
		c.hub.AddDamage(c.HeroName, c.HeroClass, damage)
	}
}

func (c *Client) sendJSON(msg ServerMessage) {
	data, err := json.Marshal(msg)
	if err != nil {
		log.Printf("Error marshaling message: %v", err)
		return
	}
	select {
	case c.send <- data:
	default:
	}
}
