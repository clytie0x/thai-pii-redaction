async page => {
  const viewports = [[1440,729],[1366,768],[1440,900],[1024,768],[768,1024],[720,365],[390,844],[360,800]];
  const paths = ["/", "/app", "/developers", "/privacy", "/help", "/terms", "/downloads", "/not-a-real-page"];
  const output = [];
  let consoleErrors = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  for (const [width, height] of viewports) {
    await page.setViewportSize({width, height});
    for (const pathname of paths) {
      consoleErrors = [];
      const response = await page.goto(`https://127.0.0.1:20270${pathname}`, {waitUntil: "networkidle"});
      const facts = await page.evaluate(async () => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        h1: document.querySelectorAll("h1").length,
        brokenImages: [...document.images].filter(image => !image.complete || image.naturalWidth === 0).length,
        lang: document.documentElement.lang,
        fontReady: document.fonts.status,
        stored: localStorage.length + sessionStorage.length,
        indexedDatabases: indexedDB.databases ? (await indexedDB.databases()).length : 0,
        cacheEntries: "caches" in window ? (await caches.keys()).length : 0,
        serviceWorkerRegistrations: navigator.serviceWorker ? (await navigator.serviceWorker.getRegistrations()).length : 0,
      }));
      output.push({pathname, width, height, status: response?.status(), overflow: facts.scrollWidth - facts.clientWidth, ...facts, consoleErrors: [...consoleErrors]});
    }
  }
  const expectedStatus = row => row.pathname === "/not-a-real-page" ? 404 : 200;
  const unexpectedConsole = row => row.consoleErrors.filter(message => {
    if (row.pathname === "/app" && /401 \(Unauthorized\)/.test(message)) return false;
    if (row.pathname === "/not-a-real-page" && /404 \(Not Found\)/.test(message)) return false;
    return true;
  });
  return {
    checks: output.length,
    overflowFailures: output.filter(row => row.overflow !== 0).map(row => [row.pathname, row.width, row.height, row.overflow]),
    statusFailures: output.filter(row => row.status !== expectedStatus(row)).map(row => [row.pathname, row.width, row.status]),
    structureFailures: output.filter(row => row.h1 !== 1 || row.brokenImages || row.fontReady !== "loaded" || row.stored || row.indexedDatabases || row.cacheEntries || row.serviceWorkerRegistrations).map(row => [row.pathname, row.width, row.h1, row.brokenImages, row.fontReady, row.stored, row.indexedDatabases, row.cacheEntries, row.serviceWorkerRegistrations]),
    unexpectedConsoleFailures: output.flatMap(row => unexpectedConsole(row).map(message => [row.pathname, row.width, message])),
    expectedSignedOut401Count: output.filter(row => row.pathname === "/app" && row.consoleErrors.some(message => /401 \(Unauthorized\)/.test(message))).length,
    expectedNavigation404Count: output.filter(row => row.pathname === "/not-a-real-page" && row.consoleErrors.some(message => /404 \(Not Found\)/.test(message))).length,
  };
}
