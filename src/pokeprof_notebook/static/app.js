const form = document.getElementById("query-form");
const input = document.getElementById("query-input");
const submitBtn = document.getElementById("submit-btn");
const resultArea = document.getElementById("result-area");
const routeInfo = document.getElementById("route-info");
const sectionsInfo = document.getElementById("sections-info");
const answerEl = document.getElementById("answer");
const errorEl = document.getElementById("error");
const loading = document.getElementById("loading");

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const query = input.value.trim();
  if (!query) return;

  const persona = document.getElementById("persona-select").value;

  // Reset UI
  resultArea.classList.add("hidden");
  routeInfo.classList.add("hidden");
  sectionsInfo.classList.add("hidden");
  errorEl.classList.add("hidden");
  answerEl.textContent = "";
  loading.classList.remove("hidden");
  submitBtn.disabled = true;

  try {
    const params = new URLSearchParams({ q: query, persona });
    const eventSource = new EventSource(`/api/query?${params}`);

    eventSource.addEventListener("route", (e) => {
      try {
        const data = JSON.parse(e.data);
        routeInfo.textContent = `Documents: ${data.documents.join(", ")} | Confidence: ${data.confidence}`;
        routeInfo.classList.remove("hidden");
      } catch {
        routeInfo.textContent = "Routing complete";
        routeInfo.classList.remove("hidden");
      }
      resultArea.classList.remove("hidden");
      loading.classList.add("hidden");
    });

    eventSource.addEventListener("sections", (e) => {
      try {
        const sections = JSON.parse(e.data);
        sectionsInfo.textContent = "";
        sections.forEach((s) => {
          const badge = document.createElement("span");
          badge.className = "badge";
          badge.textContent = `${s.section_number || s.title} (${s.document_name})`;
          sectionsInfo.appendChild(badge);
          sectionsInfo.appendChild(document.createTextNode(" "));
        });
        sectionsInfo.classList.remove("hidden");
      } catch {
        // Ignore malformed section data
      }
    });

    eventSource.addEventListener("token", (e) => {
      answerEl.textContent += e.data;
    });

    eventSource.addEventListener("error", (e) => {
      if (e.data) {
        errorEl.textContent = e.data;
        errorEl.classList.remove("hidden");
      }
      loading.classList.add("hidden");
      resultArea.classList.remove("hidden");
      eventSource.close();
      submitBtn.disabled = false;
    });

    eventSource.addEventListener("done", () => {
      eventSource.close();
      submitBtn.disabled = false;
    });

    // Handle connection errors
    eventSource.onerror = () => {
      if (eventSource.readyState === EventSource.CLOSED) return;
      errorEl.textContent = "Connection lost. Please try again.";
      errorEl.classList.remove("hidden");
      loading.classList.add("hidden");
      resultArea.classList.remove("hidden");
      eventSource.close();
      submitBtn.disabled = false;
    };
  } catch (err) {
    errorEl.textContent = `Error: ${err.message}`;
    errorEl.classList.remove("hidden");
    loading.classList.add("hidden");
    resultArea.classList.remove("hidden");
    submitBtn.disabled = false;
  }
});
