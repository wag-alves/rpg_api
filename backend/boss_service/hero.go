package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
)

type Hero struct {
	ID    string
	Name  string
	Class string
	ATK   int
}

type HeroPool struct {
	mu      sync.Mutex
	heroes  []Hero
	slots   [4]*Client
}

func NewHeroPool() *HeroPool {
	return &HeroPool{}
}

func (p *HeroPool) FetchFromGateway(gatewayURL string) error {
	resp, err := http.Get(fmt.Sprintf("%s/api/boss/hero-pool", gatewayURL))
	if err != nil {
		return fmt.Errorf("failed to fetch hero pool: %w", err)
	}
	defer resp.Body.Close()

	var raw struct {
		Data []struct {
			ID           string `json:"id"`
			Name         string `json:"nome"`
			Class        string `json:"nome_classe"`
			Estatisticas struct {
				ATK int `json:"atk"`
			} `json:"estatisticas"`
		} `json:"data"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&raw); err != nil {
		return fmt.Errorf("failed to decode hero pool: %w", err)
	}

	p.mu.Lock()
	defer p.mu.Unlock()

	p.heroes = nil
	for _, h := range raw.Data {
		p.heroes = append(p.heroes, Hero{
			ID:    h.ID,
			Name:  h.Name,
			Class: h.Class,
			ATK:   h.Estatisticas.ATK,
		})
	}
	return nil
}

func (p *HeroPool) HasHeroes() bool {
	p.mu.Lock()
	defer p.mu.Unlock()
	return len(p.heroes) > 0
}

func (p *HeroPool) AssignHero(c *Client) bool {
	p.mu.Lock()
	defer p.mu.Unlock()

	for i, slot := range p.slots {
		if slot == nil {
			for _, hero := range p.heroes {
				alreadyAssigned := false
				for _, s := range p.slots {
					if s != nil && s.HeroID == hero.ID {
						alreadyAssigned = true
						break
					}
				}
				if !alreadyAssigned {
					p.slots[i] = c
					c.HeroID = hero.ID
					c.HeroName = hero.Name
					c.HeroClass = hero.Class
					c.HeroATK = hero.ATK
					c.Slot = i + 1
					return true
				}
			}
		}
	}
	return false
}

func (p *HeroPool) ReleaseHero(c *Client) {
	p.mu.Lock()
	defer p.mu.Unlock()

	for i, slot := range p.slots {
		if slot == c {
			p.slots[i] = nil
			break
		}
	}
}

func (p *HeroPool) SlotCount() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	count := 0
	for _, s := range p.slots {
		if s != nil {
			count++
		}
	}
	return count
}
