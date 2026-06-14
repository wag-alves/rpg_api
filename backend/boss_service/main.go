package main

import (
	"encoding/json"
	"log"
	"net/http"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

var hub *Hub

func main() {
	gatewayURL := "http://localhost:8000"
	hub = NewHub(gatewayURL)

	// Fetch hero pool on startup
	if err := hub.pool.FetchFromGateway(gatewayURL); err != nil {
		log.Printf("Warning: could not fetch hero pool: %v", err)
	}

	http.HandleFunc("/ws", handleWebSocket)
	http.HandleFunc("/spawn", handleSpawn)

	go hub.Run()

	log.Println("Boss service running on :8080")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal(err)
	}
}

func handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return
	}

	client := NewClient(hub, conn)

	if !hub.pool.HasHeroes() {
		if err := hub.pool.FetchFromGateway("http://localhost:8000"); err != nil {
			log.Printf("Failed to fetch hero pool: %v", err)
		}
	}

	if !hub.pool.AssignHero(client) {
		msg, _ := json.Marshal(ServerMessage{
			Type: "lobby_full",
			Payload: map[string]string{
				"message": "Os 4 heróis já estão em batalha!",
			},
		})
		conn.WriteMessage(websocket.TextMessage, msg)
		conn.Close()
		return
	}

	hub.Register <- client

	go client.WritePump()
	go client.ReadPump()
}

func handleSpawn(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	hub.SpawnBoss()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"message": "Boss spawned!",
	})
}
