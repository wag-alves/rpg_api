package main

import (
	"log"
	"net/http"
	"strings"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin:     func(r *http.Request) bool { return true },
}

func serveWs(hub *Hub, w http.ResponseWriter, r *http.Request) {
	heroID := strings.TrimSpace(r.URL.Query().Get("hero_id"))
	if heroID == "" {
		http.Error(w, "hero_id query parameter is required", http.StatusBadRequest)
		return
	}

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("upgrade error: %v", err)
		return
	}

	client := &Client{
		hub:    hub,
		conn:   conn,
		send:   make(chan []byte, 256),
		heroID: heroID,
	}

	welcome, _ := encode(Welcome{Type: "welcome", MyID: heroID})
	client.send <- welcome

	hub.register <- client

	go client.writePump()
	go client.readPump()
}

func main() {
	hub := NewHub()
	go hub.Run()

	http.HandleFunc("/ws/trade", func(w http.ResponseWriter, r *http.Request) {
		serveWs(hub, w, r)
	})

	log.Println("Trade service listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
