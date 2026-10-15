let sharedObserver = null;

function getSharedObserver() {
  if (sharedObserver || typeof IntersectionObserver === "undefined") {
    return sharedObserver;
  }

  sharedObserver = new IntersectionObserver(
    (entries, observer) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.remove("ss-reveal-pending");
        entry.target.classList.add("ss-reveal-visible");
        observer.unobserve(entry.target);
      }
    },
    { root: null, rootMargin: "0px 0px -24px 0px", threshold: 0.08 },
  );

  return sharedObserver;
}

/** Reveal once when a product grid enters view. All grids share one observer. */
export function observeScrollReveal(element) {
  if (!element || typeof window === "undefined") return () => {};

  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  const observer = getSharedObserver();
  if (reducedMotion || !observer) return () => {};

  element.classList.add("ss-reveal-pending");
  observer.observe(element);

  return () => {
    observer.unobserve(element);
    element.classList.remove("ss-reveal-pending", "ss-reveal-visible");
  };
}
