import test from 'node:test';
import assert from 'node:assert/strict';

import { extractMeshPayload } from '../ui/mesh_parser.js';

test('extracts mesh payload from json block', () => {
  const input = `
Here is your mesh:
\`\`\`json
{"mesh":{"vertices":[[0,0,0],[1,0,0],[0,1,0]],"triangles":[[0,1,2]]}}
\`\`\`
`;
  const result = extractMeshPayload(input);
  assert.ok(result);
  assert.equal(result.vertices.length, 3);
});

test('accepts top-level mesh data', () => {
  const input = `
\`\`\`json
{"vertices":[[0,0,0],[1,0,0],[0,1,0]],"triangles":[[0,1,2]]}
\`\`\`
`;
  const result = extractMeshPayload(input);
  assert.ok(result);
  assert.ok(Array.isArray(result.triangles));
});

test('returns null on invalid json', () => {
  const input = `
\`\`\`json
{"mesh":}
\`\`\`
`;
  const result = extractMeshPayload(input);
  assert.equal(result, null);
});

test('extracts mesh payload from raw json', () => {
  const input = `{"mesh":{"vertices":[[0,0,0],[1,0,0],[0,1,0]],"triangles":[[0,1,2]]}}`;
  const result = extractMeshPayload(input);
  assert.ok(result);
  assert.equal(result.vertices.length, 3);
});

test('extracts mesh payload from non-json fenced block', () => {
  const input = `
\`\`\`
{"vertices":[[0,0,0],[1,0,0],[0,1,0]],"triangles":[[0,1,2]]}
\`\`\`
`;
  const result = extractMeshPayload(input);
  assert.ok(result);
  assert.equal(result.triangles.length, 1);
});
