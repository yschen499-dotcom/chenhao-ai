const keywords = ["RAG 与知识库", "LLM 接入与对话", "Python 工程交付", "钉钉 Bot", "AI 应用工程"];
const keywordNode = document.getElementById("keyword-rotator");
const revealNodes = document.querySelectorAll(".reveal");
const navLinks = document.querySelectorAll(".site-nav a");
const sections = [...document.querySelectorAll("main section[id]")];

let keywordIndex = 0;

if (keywordNode) {
  window.setInterval(() => {
    keywordIndex = (keywordIndex + 1) % keywords.length;
    keywordNode.textContent = keywords[keywordIndex];
  }, 2200);
}

const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
      }
    });
  },
  {
    threshold: 0.12,
  }
);

revealNodes.forEach((node) => revealObserver.observe(node));

const setActiveNav = () => {
  const scrollPosition = window.scrollY + 140;

  sections.forEach((section) => {
    const isCurrent =
      scrollPosition >= section.offsetTop &&
      scrollPosition < section.offsetTop + section.offsetHeight;

    navLinks.forEach((link) => {
      const matches = link.getAttribute("href") === `#${section.id}`;
      link.classList.toggle("active", Boolean(isCurrent && matches));
    });
  });
};

window.addEventListener("scroll", setActiveNav, { passive: true });
window.addEventListener("load", setActiveNav);
