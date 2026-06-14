package main

type ClientMessage struct {
	Type string `json:"type"`
}

type ServerMessage struct {
	Type    string      `json:"type"`
	Payload interface{} `json:"payload,omitempty"`
}

type HeroInfo struct {
	ID    string `json:"id"`
	Name  string `json:"name"`
	Class string `json:"class"`
	ATK   int    `json:"atk"`
	Slot  int    `json:"slot"`
}

type BossStatus struct {
	Name     string `json:"name"`
	HP       int    `json:"hp"`
	MaxHP    int    `json:"max_hp"`
	Timer    int    `json:"timer"`
	Active   bool   `json:"active"`
}

type DamageEntry struct {
	Name   string `json:"name"`
	Class  string `json:"class"`
	Damage int    `json:"damage"`
	Pct    float64 `json:"pct"`
}

type BossDefeated struct {
	Participants int            `json:"participants"`
	TopDamage    []DamageEntry  `json:"top_damage"`
	Duration     string         `json:"duration"`
}

type RewardInfo struct {
	HeroName string `json:"hero_name"`
	Damage   int    `json:"damage"`
	XP       int    `json:"xp"`
	Gold     int    `json:"gold"`
}

type HeroJoined struct {
	HeroName string `json:"hero_name"`
	Class    string `json:"class"`
	Slot     int    `json:"slot"`
}

type HeroLeft struct {
	HeroName string `json:"hero_name"`
	Slot     int    `json:"slot"`
}

type DamageDealt struct {
	HP       int    `json:"hp"`
	MaxHP    int    `json:"max_hp"`
	Attacker string `json:"attacker_name"`
	Damage   int    `json:"damage"`
}
