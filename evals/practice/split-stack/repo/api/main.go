// The stock API: a JSON file store behind two routes.
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"sync"
)

var version = "dev"

type Item struct {
	Name string `json:"name"`
	Qty  int    `json:"qty"`
}

type Store struct {
	path string
	mu   sync.Mutex
}

func (s *Store) read() ([]Item, error) {
	data, err := os.ReadFile(s.path)
	if os.IsNotExist(err) {
		return []Item{}, nil
	}
	if err != nil {
		return nil, err
	}
	var items []Item
	return items, json.Unmarshal(data, &items)
}

func (s *Store) write(items []Item) error {
	if err := os.MkdirAll(filepath.Dir(s.path), 0o755); err != nil {
		return err
	}
	data, _ := json.MarshalIndent(items, "", "  ")
	return os.WriteFile(s.path, data, 0o644)
}

func reply(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(body)
}

func main() {
	store := &Store{path: env("STOCK_DATA", "data/items.json")}
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) { reply(w, 200, map[string]string{"status": "ok"}) })
	http.HandleFunc("/version", func(w http.ResponseWriter, r *http.Request) { reply(w, 200, map[string]string{"version": version}) })
	http.HandleFunc("/items", func(w http.ResponseWriter, r *http.Request) {
		store.mu.Lock()
		defer store.mu.Unlock()
		items, err := store.read()
		if err != nil {
			reply(w, 500, map[string]string{"error": err.Error()})
			return
		}
		switch r.Method {
		case http.MethodGet:
			reply(w, 200, items)
		case http.MethodPost:
			var item Item
			if err := json.NewDecoder(r.Body).Decode(&item); err != nil || item.Name == "" {
				reply(w, 400, map[string]string{"error": "name and qty are required"})
				return
			}
			if item.Qty < 0 {
				reply(w, 400, map[string]string{"error": "qty must be zero or more"})
				return
			}
			items = append(items, item)
			if err := store.write(items); err != nil {
				reply(w, 500, map[string]string{"error": err.Error()})
				return
			}
			reply(w, 201, item)
		default:
			reply(w, 405, map[string]string{"error": "method not allowed"})
		}
	})
	addr := "127.0.0.1:" + env("STOCK_PORT", "8075")
	fmt.Printf("stock-api %s listening on http://%s, data in %s\n", version, addr, store.path)
	if err := http.ListenAndServe(addr, nil); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
