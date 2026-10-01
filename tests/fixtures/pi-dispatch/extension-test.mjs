// Offline factory/event tests: no pi process, credentials, provider or network.
import assert from "node:assert/strict";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
const { default: extension } = await import(pathToFileURL(resolve(process.argv[2])));
const model = { provider: "openai-codex", api: "openai-codex-responses", id: "gpt-6.1-sol" };
const payload = Object.freeze({ model: model.id, input: [], instructions: "PRIVATE-PAYLOAD-MARKER", stream: true });
let cases = 0;
function handler(tier) {
  if (tier === undefined) delete process.env.PI_DISPATCH_SERVICE_TIER;
  else process.env.PI_DISPATCH_SERVICE_TIER = tier;
  const handlers = [];
  extension({ on(name, fn) {
    assert.equal(name, "before_provider_request"); handlers.push(fn);
  } });
  return handlers[0];
}
const onRequest = handler("priority");
assert.deepEqual(onRequest({ payload }, { model }), { ...payload, service_tier: "priority" }); cases++;
assert.equal(payload.service_tier, undefined); cases++;
assert.deepEqual(onRequest({ payload }, { model: { ...model, api: "openai-responses" } }),
                 { ...payload, service_tier: "priority" }); cases++;
assert.equal(onRequest({ payload: { ...payload, service_tier: "default" } }, { model }).service_tier,
             "priority"); cases++;
for (const other of [
  { ...model, provider: "anthropic", api: "anthropic-messages" },
  { ...model, provider: "openai", api: "openai-responses" },
  { ...model, provider: "azure-openai", api: "openai-responses" },
  { ...model, api: "openai-completions" },
  { ...model, id: "another-model" }, undefined,
]) {
  assert.equal(onRequest({ payload }, { model: other }), undefined); cases++;
}
for (const other of [null, [], "PRIVATE-PAYLOAD-MARKER", {},
  { ...payload, model: "other" }, { ...payload, input: "text" },
  { ...payload, instructions: null }, { ...payload, messages: [] },
]) {
  assert.equal(onRequest({ payload: other }, { model }), undefined); cases++;
}
assert.equal(onRequest(undefined, undefined), undefined); cases++;
assert.equal(handler(undefined), undefined); cases++;
for (const invalid of ["fast", "default", "auto", "PRIORITY", "", "PRIVATE-PAYLOAD-MARKER\n"] ) {
  assert.equal(handler(invalid), undefined); cases++;
}
console.log(JSON.stringify({ cases }));
