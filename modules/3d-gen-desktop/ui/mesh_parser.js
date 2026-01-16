function extractJsonCandidates(text) {
  const candidates = [];
  const fenceRegex = /```(?:json)?\s*([\s\S]*?)```/gi;
  let match = null;
  while ((match = fenceRegex.exec(text)) !== null) {
    if (match[1]) {
      candidates.push(match[1].trim());
    }
  }

  const trimmed = text.trim();
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    candidates.push(trimmed);
  }

  if (!candidates.length) {
    const firstBrace = text.indexOf('{');
    const lastBrace = text.lastIndexOf('}');
    if (firstBrace !== -1 && lastBrace > firstBrace) {
      candidates.push(text.slice(firstBrace, lastBrace + 1).trim());
    }
  }

  return candidates;
}

function coerceMeshPayload(payload) {
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  if (payload.mesh && typeof payload.mesh === 'object') {
    return payload.mesh;
  }
  if (payload.vertices && payload.triangles) {
    return payload;
  }
  return null;
}

export function extractMeshPayload(text) {
  const candidates = extractJsonCandidates(text);
  for (const candidate of candidates) {
    try {
      const payload = JSON.parse(candidate);
      const mesh = coerceMeshPayload(payload);
      if (mesh) {
        return mesh;
      }
    } catch (error) {
      continue;
    }
  }
  return null;
}
