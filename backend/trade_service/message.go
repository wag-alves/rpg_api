package main

import "encoding/json"

type Welcome struct {
	Type string `json:"type"`
	MyID string `json:"my_id"`
}

type LobbyUpdate struct {
	Type          string   `json:"type"`
	OnlinePlayers []string `json:"online_players"`
}

type TradeRequest struct {
	Type   string `json:"type"`
	FromID string `json:"from_id"`
	ToID   string `json:"to_id"`
}

type TradeAccept struct {
	Type   string `json:"type"`
	FromID string `json:"from_id"`
	ToID   string `json:"to_id"`
}

type TradeDecline struct {
	Type   string `json:"type"`
	FromID string `json:"from_id"`
	ToID   string `json:"to_id"`
}

type ItemOffer struct {
	Type   string `json:"type"`
	FromID string `json:"from_id"`
	ItemID string `json:"item_id"`
}

type TradeConfirm struct {
	Type string `json:"type"`
}

type TradeComplete struct {
	Type string `json:"type"`
}

type TradeCancel struct {
	Type   string `json:"type"`
	FromID string `json:"from_id"`
}

func encode(v any) ([]byte, error) {
	return json.Marshal(v)
}
