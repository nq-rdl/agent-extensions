package main

import (
	"github.com/spf13/cobra"
)

const defaultServerURL = "http://localhost:4097"

func newRootCmd() *cobra.Command {
	root := &cobra.Command{
		Use:   "pi-cli",
		Short: "CLI wrapper for pi.dev ConnectRPC sessions",
		Long: `pi-cli manages pi.dev coding agent sessions via the pi-server ConnectRPC service.

Start pi-server first:
  cd skills/pi-rpc/scripts && make serve

Then use pi-cli to create and communicate with sessions:
  pi-cli session create --provider anthropic --model claude-opus-4
  pi-cli session prompt --id <session-id> "Create a hello world program"
  pi-cli session list
  pi-cli session delete --id <session-id>

Set PI_SERVER_URL to override the default server address (http://localhost:4097).`,
	}

	root.AddCommand(
		newServeCmd(),
		newSessionCmd(),
	)

	return root
}
