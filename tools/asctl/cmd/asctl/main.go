package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"

	"charm.land/fang/v2"
	"github.com/spf13/cobra"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/parser"
	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/prompt"
	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/repocheck"
	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/validator"
)

var (
	version = "dev"
	commit  = "none"
)

func main() {
	if err := fang.Execute(
		context.Background(),
		newRootCmd(),
		fang.WithVersion(version),
		fang.WithCommit(commit),
	); err != nil {
		os.Exit(1)
	}
}

func newRootCmd() *cobra.Command {
	root := &cobra.Command{
		Use:   "asctl",
		Short: "Agent Skills control — validate, inspect, and render skills",
	}
	root.AddCommand(
		newValidateCmd(),
		newReadPropertiesCmd(),
		newToPromptCmd(),
		newRepoCheckCmd(),
	)
	return root
}

func newValidateCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "validate <skill-dir>...",
		Short: "Validate one or more skill directories",
		Args:  cobra.MinimumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			var hasErrors bool
			for _, dir := range args {
				for _, e := range validator.Validate(dir) {
					fmt.Fprintf(cmd.ErrOrStderr(), "%s: %s\n", dir, e)
					hasErrors = true
				}
			}
			if hasErrors {
				return fmt.Errorf("validation failed")
			}
			return nil
		},
	}
}

func newReadPropertiesCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "read-properties <skill-dir>",
		Short: "Print parsed SKILL.md properties as JSON",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			props, err := parser.ReadProperties(args[0])
			if err != nil {
				return err
			}
			enc := json.NewEncoder(cmd.OutOrStdout())
			enc.SetIndent("", "  ")
			return enc.Encode(props)
		},
	}
}

func newToPromptCmd() *cobra.Command {
	var skillsRoot string
	c := &cobra.Command{
		Use:   "to-prompt [skill-dir]...",
		Short: "Generate <available_skills> XML block",
		Long: `Generate the <available_skills> XML block for inclusion in agent system prompts.
If no skill directories are provided, all skills under --skills-root are included.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			dirs := args
			if len(dirs) == 0 {
				var err error
				dirs, err = repocheck.IterSkillDirs(skillsRoot)
				if err != nil {
					return err
				}
			}
			out, err := prompt.ToPrompt(dirs)
			if err != nil {
				return err
			}
			fmt.Fprintln(cmd.OutOrStdout(), out)
			return nil
		},
	}
	c.Flags().StringVar(&skillsRoot, "skills-root", "skills", "root directory containing skill subdirectories")
	return c
}

func newRepoCheckCmd() *cobra.Command {
	var skillsRoot string
	c := &cobra.Command{
		Use:   "repo-check [path]...",
		Short: "Validate all skills in the repository",
		Long: `Validate all skills under --skills-root. If paths are provided, only the
affected skill directories are validated (pre-commit mode).`,
		RunE: func(cmd *cobra.Command, args []string) error {
			skillDirs, err := repocheck.ResolveSkillDirs(args, skillsRoot)
			if err != nil {
				return err
			}
			if len(skillDirs) == 0 {
				fmt.Fprintln(cmd.OutOrStdout(), "No skill directories selected for validation.")
				return nil
			}
			errs := repocheck.ValidateSkillDirs(skillDirs)
			if len(errs) > 0 {
				for _, e := range errs {
					fmt.Fprintln(cmd.ErrOrStderr(), e)
				}
				return fmt.Errorf("validation failed: %d error(s)", len(errs))
			}
			fmt.Fprintf(cmd.OutOrStdout(), "Validated %d skill(s) and generated <available_skills> XML.\n", len(skillDirs))
			return nil
		},
	}
	c.Flags().StringVar(&skillsRoot, "skills-root", "skills", "root directory containing skill subdirectories")
	return c
}
