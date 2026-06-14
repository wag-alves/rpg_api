package main

import (
	"math/rand"
	"sync"
	"time"
)

type Boss struct {
	mu       sync.Mutex
	Name     string
	HP       int
	MaxHP    int
	Active   bool
	Timer    time.Duration
	startedAt time.Time
	hub      *Hub
}

func NewBoss(hub *Hub) *Boss {
	return &Boss{
		Name:  "Dragão de Gelo de Vorheim",
		MaxHP: 5000,
		HP:    5000,
		Timer: 5 * time.Minute,
		hub:   hub,
	}
}

func (b *Boss) Spawn() {
	b.mu.Lock()
	b.HP = b.MaxHP
	b.Active = true
	b.startedAt = time.Now()
	b.mu.Unlock()

	b.hub.Broadcast(ServerMessage{
		Type: "boss_spawn",
		Payload: BossStatus{
			Name:   b.Name,
			HP:     b.HP,
			MaxHP:  b.MaxHP,
			Timer:  int(b.Timer.Seconds()),
			Active: true,
		},
	})
}

func (b *Boss) TakeDamage(attacker string, atk int) int {
	b.mu.Lock()
	defer b.mu.Unlock()

	if !b.Active || b.HP <= 0 {
		return 0
	}

	variance := 0.8 + rand.Float64()*0.4
	damage := int(float64(atk) * variance)
	if damage < 1 {
		damage = 1
	}

	b.HP -= damage
	if b.HP < 0 {
		b.HP = 0
	}

	b.hub.Broadcast(ServerMessage{
		Type: "boss_hp",
		Payload: DamageDealt{
			HP:       b.HP,
			MaxHP:    b.MaxHP,
			Attacker: attacker,
			Damage:   damage,
		},
	})

	if b.HP <= 0 {
		b.Active = false
		b.hub.OnBossDefeated()
	}

	return damage
}

func (b *Boss) IsActive() bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.Active
}

func (b *Boss) GetStatus() BossStatus {
	b.mu.Lock()
	defer b.mu.Unlock()
	elapsed := time.Since(b.startedAt)
	remaining := b.Timer - elapsed
	if remaining < 0 {
		remaining = 0
	}
	return BossStatus{
		Name:   b.Name,
		HP:     b.HP,
		MaxHP:  b.MaxHP,
		Timer:  int(remaining.Seconds()),
		Active: b.Active,
	}
}

func (b *Boss) RunTimer() {
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		b.mu.Lock()
		if !b.Active {
			b.mu.Unlock()
			return
		}
		elapsed := time.Since(b.startedAt)
		if elapsed >= b.Timer {
			b.Active = false
			b.mu.Unlock()
			b.hub.Broadcast(ServerMessage{Type: "boss_escaped"})
			return
		}
		remaining := b.Timer - elapsed
		hp := b.HP
		maxHp := b.MaxHP
		name := b.Name
		b.mu.Unlock()

		b.hub.Broadcast(ServerMessage{
			Type: "boss_status",
			Payload: BossStatus{
				Name:   name,
				HP:     hp,
				MaxHP:  maxHp,
				Timer:  int(remaining.Seconds()),
				Active: true,
			},
		})
	}
}
