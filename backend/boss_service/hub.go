package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sort"
	"sync"
	"time"
)

type Hub struct {
	mu           sync.RWMutex
	clients      map[*Client]bool
	Register     chan *Client
	Unregister   chan *Client
	boss         *Boss
	pool         *HeroPool
	damageMap    map[string]int
	damageClass  map[string]string
	gatewayURL   string
}

func NewHub(gatewayURL string) *Hub {
	h := &Hub{
		clients:     make(map[*Client]bool),
		Register:    make(chan *Client),
		Unregister:  make(chan *Client),
		damageMap:   make(map[string]int),
		damageClass: make(map[string]string),
		gatewayURL:  gatewayURL,
	}
	h.boss = NewBoss(h)
	h.pool = NewHeroPool()
	return h
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.Register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()

			client.sendJSON(ServerMessage{
				Type: "welcome",
				Payload: HeroInfo{
					ID:    client.HeroID,
					Name:  client.HeroName,
					Class: client.HeroClass,
					ATK:   client.HeroATK,
					Slot:  client.Slot,
				},
			})

			status := h.boss.GetStatus()
			client.sendJSON(ServerMessage{
				Type:    "boss_status",
				Payload: status,
			})

			h.Broadcast(ServerMessage{
				Type: "hero_joined",
				Payload: HeroJoined{
					HeroName: client.HeroName,
					Class:    client.HeroClass,
					Slot:     client.Slot,
				},
			})

			log.Printf("Hero joined: %s (%s) slot %d", client.HeroName, client.HeroClass, client.Slot)

		case client := <-h.Unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
			}
			h.mu.Unlock()

			h.pool.ReleaseHero(client)

			h.Broadcast(ServerMessage{
				Type: "hero_left",
				Payload: HeroLeft{
					HeroName: client.HeroName,
					Slot:     client.Slot,
				},
			})

			log.Printf("Hero left: %s", client.HeroName)
		}
	}
}

func (h *Hub) Broadcast(msg ServerMessage) {
	data, err := json.Marshal(msg)
	if err != nil {
		log.Printf("Error marshaling broadcast: %v", err)
		return
	}

	h.mu.RLock()
	defer h.mu.RUnlock()

	for client := range h.clients {
		select {
		case client.send <- data:
		default:
			close(client.send)
			delete(h.clients, client)
		}
	}
}

func (h *Hub) AddDamage(name, class string, damage int) {
	h.mu.Lock()
	h.damageMap[name] += damage
	h.damageClass[name] = class
	total := 0
	for _, d := range h.damageMap {
		total += d
	}
	h.mu.Unlock()

	h.broadcastTopDamage()
}

func (h *Hub) broadcastTopDamage() {
	h.mu.RLock()
	total := 0
	type entry struct {
		name  string
		class string
		dmg   int
	}
	var entries []entry
	for name, dmg := range h.damageMap {
		total += dmg
		entries = append(entries, entry{
			name:  name,
			class: h.damageClass[name],
			dmg:   dmg,
		})
	}
	h.mu.RUnlock()

	sort.Slice(entries, func(i, j int) bool {
		return entries[i].dmg > entries[j].dmg
	})

	top := entries
	if len(top) > 5 {
		top = top[:5]
	}

	var topPayload []DamageEntry
	for _, e := range top {
		pct := 0.0
		if total > 0 {
			pct = float64(e.dmg) / float64(total) * 100
		}
		topPayload = append(topPayload, DamageEntry{
			Name:   e.name,
			Class:  e.class,
			Damage: e.dmg,
			Pct:    pct,
		})
	}

	h.Broadcast(ServerMessage{
		Type:    "top_damage",
		Payload: topPayload,
	})
}

func (h *Hub) OnBossDefeated() {
	h.mu.RLock()
	participants := len(h.clients)
	duration := time.Since(h.boss.startedAt).Round(time.Second).String()

	type entry struct {
		name   string
		class  string
		damage int
	}
	var entries []entry
	totalDamage := 0
	for name, dmg := range h.damageMap {
		entries = append(entries, entry{name: name, class: h.damageClass[name], damage: dmg})
		totalDamage += dmg
	}
	h.mu.RUnlock()

	sort.Slice(entries, func(i, j int) bool {
		return entries[i].damage > entries[j].damage
	})

	top := entries
	if len(top) > 5 {
		top = top[:5]
	}

	var topPayload []DamageEntry
	for _, e := range top {
		pct := 0.0
		if totalDamage > 0 {
			pct = float64(e.damage) / float64(totalDamage) * 100
		}
		topPayload = append(topPayload, DamageEntry{
			Name:   e.name,
			Class:  e.class,
			Damage: e.damage,
			Pct:    pct,
		})
	}

	h.Broadcast(ServerMessage{
		Type: "boss_defeated",
		Payload: BossDefeated{
			Participants: participants,
			TopDamage:    topPayload,
			Duration:     duration,
		},
	})

	// Distribute rewards proportionally
	h.mu.RLock()
	rewardPoolXP := 500
	rewardPoolGold := 200
	var clientList []*Client
	for c := range h.clients {
		clientList = append(clientList, c)
	}
	h.mu.RUnlock()

	for _, c := range clientList {
		h.mu.RLock()
		dmg := h.damageMap[c.HeroName]
		h.mu.RUnlock()

		xp := 0
		gold := 0
		if totalDamage > 0 {
			pct := float64(dmg) / float64(totalDamage)
			xp = int(float64(rewardPoolXP) * pct)
			gold = int(float64(rewardPoolGold) * pct)
		}
		if xp < 10 {
			xp = 10
		}
		if gold < 5 {
			gold = 5
		}

		c.sendJSON(ServerMessage{
			Type: "reward",
			Payload: RewardInfo{
				HeroName: c.HeroName,
				Damage:   dmg,
				XP:       xp,
				Gold:     gold,
			},
		})

		// Persist rewards to hero service via gateway
		go func(clientID string, xp, gold int) {
			httpClient := &http.Client{Timeout: 3 * time.Second}
			payload := fmt.Sprintf(`{"quantidade": %d}`, xp)
			httpClient.Post(
				fmt.Sprintf("%s/api/heroes/%s/xp", h.gatewayURL, clientID),
				"application/json",
				jsonRaw(payload),
			)
			payload2 := fmt.Sprintf(`{"quantidade": %d}`, gold)
			httpClient.Post(
				fmt.Sprintf("%s/api/heroes/%s/gold", h.gatewayURL, clientID),
				"application/json",
				jsonRaw(payload2),
			)
		}(c.HeroID, xp, gold)
	}

	// Reset damage map
	h.mu.Lock()
	h.damageMap = make(map[string]int)
	h.damageClass = make(map[string]string)
	h.mu.Unlock()

	// Auto respawn after 2 minutes
	go func() {
		time.Sleep(2 * time.Minute)
		h.SpawnBoss()
	}()
}

func (h *Hub) SpawnBoss() {
	h.boss.Spawn()
	go h.boss.RunTimer()
}

type jsonRaw string

func (j jsonRaw) Read(p []byte) (n int, err error) {
	return copy(p, []byte(j)), nil
}
