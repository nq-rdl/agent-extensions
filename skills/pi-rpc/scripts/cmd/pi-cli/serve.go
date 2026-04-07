package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/spf13/cobra"

	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/gen/pirpc/v1/pirpcv1connect"
	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/handler"
	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/internal/config"
	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/session"
)

func newServeCmd() *cobra.Command {
	var (
		port            string
		binary          string
		defaultProvider string
		defaultModel    string
	)

	cmd := &cobra.Command{
		Use:   "serve",
		Short: "Start the pi-server ConnectRPC service",
		Long: `Start the pi-server ConnectRPC service that manages pi.dev sessions.

The server listens for HTTP/JSON requests and spawns pi.dev subprocesses
on demand. Agents communicate with it via the session subcommands.

Environment variables:
  PI_SERVER_PORT       Override the listening port (default: 4097)
  PI_BINARY            Path to the pi binary (default: pi)
  PI_DEFAULT_PROVIDER  Fallback provider when Create omits it (default: openai)
  PI_DEFAULT_MODEL     Fallback model when Create omits it (default: gpt-4.1)`,
		RunE: func(cmd *cobra.Command, args []string) error {
			return runServe(port, binary, defaultProvider, defaultModel)
		},
	}

	cmd.Flags().StringVar(&port, "port", "", "Listening port (overrides PI_SERVER_PORT, default: 4097)")
	cmd.Flags().StringVar(&binary, "binary", "", "Path to pi binary (overrides PI_BINARY, default: pi)")
	cmd.Flags().StringVar(&defaultProvider, "default-provider", "", "Fallback provider (overrides PI_DEFAULT_PROVIDER, default: openai)")
	cmd.Flags().StringVar(&defaultModel, "default-model", "", "Fallback model (overrides PI_DEFAULT_MODEL, default: gpt-4.1)")

	return cmd
}

func runServe(portFlag, binaryFlag, defaultProviderFlag, defaultModelFlag string) error {
	port := portFlag
	if port == "" {
		port = os.Getenv("PI_SERVER_PORT")
	}
	if port == "" {
		port = "4097"
	}

	binary := binaryFlag
	if binary == "" {
		binary = os.Getenv("PI_BINARY")
	}
	if binary == "" {
		binary = "pi"
	}

	defaultProvider := defaultProviderFlag
	if defaultProvider == "" {
		defaultProvider = os.Getenv("PI_DEFAULT_PROVIDER")
	}
	if defaultProvider == "" {
		defaultProvider = config.DetectProvider()
	}

	defaultModel := defaultModelFlag
	if defaultModel == "" {
		defaultModel = os.Getenv("PI_DEFAULT_MODEL")
	}
	if defaultModel == "" {
		defaultModel = "gpt-4.1"
	}

	mgr := session.NewManager(binary)

	mux := http.NewServeMux()
	path, svcHandler := pirpcv1connect.NewSessionServiceHandler(handler.NewSessionHandler(mgr, handler.Defaults{
		Provider: defaultProvider,
		Model:    defaultModel,
	}))
	mux.Handle(path, svcHandler)

	addr := fmt.Sprintf(":%s", port)
	srv := &http.Server{Addr: addr, Handler: mux}

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)

	go func() {
		<-sigCh
		log.Println("shutting down — terminating all sessions")
		mgr.GracefulShutdown()
		srv.Shutdown(context.Background()) //nolint:errcheck
	}()

	log.Printf("pi-server listening on %s", addr)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		return fmt.Errorf("server error: %w", err)
	}
	return nil
}
