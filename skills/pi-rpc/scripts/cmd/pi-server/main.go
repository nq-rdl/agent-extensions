package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/gen/pirpc/v1/pirpcv1connect"
	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/handler"
	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/session"
)

func main() {
	port := os.Getenv("PI_SERVER_PORT")
	if port == "" {
		port = "4097"
	}

	mgr := session.NewManager("pi")
	h := handler.NewSessionHandler(mgr)

	mux := http.NewServeMux()
	path, svcHandler := pirpcv1connect.NewSessionServiceHandler(h)
	mux.Handle(path, svcHandler)

	addr := fmt.Sprintf(":%s", port)
	srv := &http.Server{Addr: addr, Handler: mux}

	// Graceful shutdown
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)

	go func() {
		<-sigCh
		log.Println("shutting down — terminating all sessions")
		mgr.GracefulShutdown()
		srv.Close()
	}()

	log.Printf("pi-server listening on %s", addr)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("server error: %v", err)
	}
}
