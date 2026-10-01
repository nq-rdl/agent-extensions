// Maintainer-approved plain ESM pi extension asset; no dependencies or payload logging.
// Verified pi 0.99.1 before_provider_request API, 2026-10-01.
export default function serviceTier(pi) {
  const tier = process.env.PI_DISPATCH_SERVICE_TIER;
  if (tier === undefined) return;
  if (tier !== "priority") {
    process.stderr.write("pi-dispatch: unsupported service tier; only priority is allowed; requests unchanged.\n");
    return;
  }
  pi.on("before_provider_request", (event, ctx) => {
    const model = ctx?.model;
    const payload = event?.payload;
    // The event carries only payload, not provider identity. Require the selected
    // model AND Responses shape/id to agree; never modify other providers/APIs.
    if (model?.provider !== "openai-codex" ||
        !["openai-codex-responses", "openai-responses"].includes(model.api) ||
        !payload || typeof payload !== "object" || Array.isArray(payload) ||
        typeof model.id !== "string" || payload.model !== model.id ||
        !Array.isArray(payload.input) || typeof payload.instructions !== "string" ||
        "messages" in payload) return;
    return { ...payload, service_tier: "priority" };
  });
}
