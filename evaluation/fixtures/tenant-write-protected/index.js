// Evaluation fixture only. Do not deploy.
function updateDocument(store, callerId, documentId, changes) {
  const document = store.get(documentId);
  if (!document || document.ownerId !== callerId) return false;
  store.set(documentId, { ...document, ...changes });
  return true;
}

module.exports = { updateDocument };
