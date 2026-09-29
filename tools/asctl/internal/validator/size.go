package validator

import "strings"

// BodySize describes the raw body after frontmatter, including whitespace.
type BodySize struct {
	Lines        int
	ApproxTokens float64
}

// MeasureBody counts LF-terminated lines (including CRLF) and an unterminated
// last line. A final newline adds no extra line; leading/trailing blank lines
// count. ApproxTokens is raw UTF-8 bytes / 4, not a tokenizer measurement.
func MeasureBody(body string) BodySize {
	lines := strings.Count(body, "\n")
	if body != "" && !strings.HasSuffix(body, "\n") {
		lines++
	}
	return BodySize{Lines: lines, ApproxTokens: float64(len(body)) / 4}
}
