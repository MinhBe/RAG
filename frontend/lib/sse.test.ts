import { test } from "node:test";
import assert from "node:assert/strict";
import { createSSEParser, type SSEMessage } from "./sse.ts";

test("parses events split across chunks", () => {
  const got: SSEMessage[] = [];
  const parser = createSSEParser((m) => got.push(m));
  parser.feed('event: token\ndata: {"text":"Xin ');
  parser.feed('chào"}\n\nevent: done\r\ndata: {}\r\n\r\n');
  assert.deepEqual(got, [
    { event: "token", data: '{"text":"Xin chào"}' },
    { event: "done", data: "{}" },
  ]);
});

test("ignores comments and joins multi-line data", () => {
  const got: SSEMessage[] = [];
  const parser = createSSEParser((m) => got.push(m));
  parser.feed(": ping\n\ndata: a\ndata: b\n\n");
  assert.deepEqual(got, [{ event: "message", data: "a\nb" }]);
});

test("flush dispatches a trailing event without blank line", () => {
  const got: SSEMessage[] = [];
  const parser = createSSEParser((m) => got.push(m));
  parser.feed("event: done\ndata: {}");
  assert.equal(got.length, 0);
  parser.flush();
  assert.deepEqual(got, [{ event: "done", data: "{}" }]);
});
