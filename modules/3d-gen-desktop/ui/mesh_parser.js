export function extractMeshPayload(text) {
  const blockMatch = text.match(/```json\s*([\s\S]*?)```/i);
  const jsonString = blockMatch ? blockMatch[1] : null;

  if (!jsonString) {
    return null;
  }

  try {
    const payload = JSON.parse(jsonString);
    if (payload.mesh) {
      return payload.mesh;
    }
    if (payload.vertices && payload.triangles) {
      return payload;
    }
  } catch (error) {
    return null;
  }

  return null;
}
