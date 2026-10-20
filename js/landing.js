/**
 * landing.js — Pulse / AIOps Sentinel Award-Winning Motion & Interaction Script
 * Uses: GSAP, ScrollTrigger, Lenis Smooth Scroll, Lucide Icons
 */

document.addEventListener("DOMContentLoaded", () => {
  // Initialize Lucide icons
  if (window.lucide) {
    window.lucide.createIcons();
  }

  initPreloader();
  initLenis();
  initCustomCursor();
  initScrollProgress();
  initNavbar();
  initHeroAnimations();
  initTiltMockup();
  initBentoSpotlight();
  initScrollStorytelling();
  initHorizontalShowcase();
  initPricingToggle();
  initTestimonialsCarousel();
  initFaqAccordion();
});

/* ──────────────────────────────────────────────────────────────
   1. Page Load Preloader
   ────────────────────────────────────────────────────────────── */
function initPreloader() {
  const preloader = document.getElementById("page-preloader");
  window.addEventListener("load", () => {
    setTimeout(() => {
      if (preloader) preloader.classList.add("loaded");
    }, 400);
  });
  // Fallback timeout in case window load fires early
  setTimeout(() => {
    if (preloader) preloader.classList.add("loaded");
  }, 1200);
}

/* ──────────────────────────────────────────────────────────────
   2. Lenis Smooth Scroll
   ────────────────────────────────────────────────────────────── */
let lenisInstance = null;
function initLenis() {
  if (typeof Lenis !== "undefined") {
    lenisInstance = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      direction: 'vertical',
      smooth: true
    });

    function raf(time) {
      lenisInstance.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);

    // Synchronize Lenis with GSAP ScrollTrigger
    if (window.gsap && window.ScrollTrigger) {
      lenisInstance.on('scroll', ScrollTrigger.update);
      gsap.ticker.add((time) => {
        lenisInstance.raf(time * 1000);
      });
      gsap.ticker.lagSmoothing(0);
    }
  }
}

/* ──────────────────────────────────────────────────────────────
   3. Interactive Custom Cursor
   ────────────────────────────────────────────────────────────── */
function initCustomCursor() {
  const dot = document.querySelector(".custom-cursor-dot");
  const follower = document.querySelector(".custom-cursor-follower");

  if (!dot || !follower) return;

  let mouseX = 0, mouseY = 0;
  let followerX = 0, followerY = 0;

  window.addEventListener("mousemove", (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;

    dot.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0)`;
  });

  function renderCursor() {
    followerX += (mouseX - followerX) * 0.15;
    followerY += (mouseY - followerY) * 0.15;
    follower.style.transform = `translate3d(${followerX}px, ${followerY}px, 0)`;
    requestAnimationFrame(renderCursor);
  }
  requestAnimationFrame(renderCursor);

  // Hover state expansions
  const hoverTargets = document.querySelectorAll("a, button, .bento-card, .faq-trigger, .pricing-card");
  hoverTargets.forEach(el => {
    el.addEventListener("mouseenter", () => follower.classList.add("cursor-hover"));
    el.addEventListener("mouseleave", () => follower.classList.remove("cursor-hover"));
  });
}

/* ──────────────────────────────────────────────────────────────
   4. Scroll Progress Bar
   ────────────────────────────────────────────────────────────── */
function initScrollProgress() {
  const progressBar = document.getElementById("scroll-progress-bar");
  if (!progressBar) return;

  window.addEventListener("scroll", () => {
    const totalScroll = document.documentElement.scrollHeight - window.innerHeight;
    const progress = totalScroll > 0 ? (window.scrollY / totalScroll) * 100 : 0;
    progressBar.style.width = `${progress}%`;
  });
}

/* ──────────────────────────────────────────────────────────────
   5. Sticky Glass Navbar & Mobile Menu
   ────────────────────────────────────────────────────────────── */
function initNavbar() {
  const navbar = document.getElementById("navbar");
  const mobileToggle = document.getElementById("mobile-toggle");
  const mobileMenu = document.getElementById("mobile-menu");

  window.addEventListener("scroll", () => {
    if (window.scrollY > 40) {
      navbar.classList.add("scrolled");
    } else {
      navbar.classList.remove("scrolled");
    }
  });

  if (mobileToggle && mobileMenu) {
    mobileToggle.addEventListener("click", () => {
      mobileMenu.classList.toggle("open");
    });
  }
}

/* ──────────────────────────────────────────────────────────────
   6. Hero Reveal & Counter Animations
   ────────────────────────────────────────────────────────────── */
function initHeroAnimations() {
  if (!window.gsap) return;

  // Split-text headline animation
  const headline = document.querySelector(".hero-headline");
  if (headline) {
    gsap.from(".hero-headline", {
      opacity: 0,
      y: 40,
      duration: 1,
      ease: "power3.out"
    });

    gsap.from(".hero-subtitle", {
      opacity: 0,
      y: 30,
      duration: 1,
      delay: 0.2,
      ease: "power3.out"
    });

    gsap.from(".hero-cta-group", {
      opacity: 0,
      y: 20,
      duration: 0.8,
      delay: 0.35,
      ease: "power3.out"
    });

    gsap.from(".hero-stats-row", {
      opacity: 0,
      scale: 0.95,
      duration: 0.8,
      delay: 0.45,
      ease: "power3.out"
    });
  }

  // Count up numbers
  const counters = document.querySelectorAll(".stat-number[data-target]");
  counters.forEach(counter => {
    const target = parseFloat(counter.getAttribute("data-target"));
    const suffix = counter.getAttribute("data-suffix") || "";
    const isFloat = counter.getAttribute("data-float") === "true";

    gsap.to(counter, {
      scrollTrigger: {
        trigger: counter,
        start: "top 90%"
      },
      innerHTML: target,
      duration: 2,
      ease: "power2.out",
      snap: { innerHTML: isFloat ? 0.01 : 1 },
      onUpdate: function () {
        const val = isFloat ? parseFloat(this.targets()[0].innerHTML).toFixed(2) : Math.floor(this.targets()[0].innerHTML);
        counter.innerHTML = `${val}${suffix}`;
      }
    });
  });
}

/* ──────────────────────────────────────────────────────────────
   7. 3D Tilt Product Mockup
   ────────────────────────────────────────────────────────────── */
function initTiltMockup() {
  const container = document.querySelector(".mockup-container");
  const card = document.querySelector(".mockup-card");

  if (!container || !card) return;

  container.addEventListener("mousemove", (e) => {
    const rect = container.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const rotateX = ((y - centerY) / centerY) * -10;
    const rotateY = ((x - centerX) / centerX) * 10;

    card.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`;
  });

  container.addEventListener("mouseleave", () => {
    card.style.transform = `rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`;
  });
}

/* ──────────────────────────────────────────────────────────────
   8. Bento Grid Spotlight Effect
   ────────────────────────────────────────────────────────────── */
function initBentoSpotlight() {
  const cards = document.querySelectorAll(".bento-card");
  cards.forEach(card => {
    card.addEventListener("mousemove", (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      card.style.setProperty("--spotlight-x", `${x}px`);
      card.style.setProperty("--spotlight-y", `${y}px`);
    });
  });

  if (window.gsap && window.ScrollTrigger) {
    gsap.from(".bento-card", {
      scrollTrigger: {
        trigger: ".bento-grid",
        start: "top 80%"
      },
      y: 40,
      opacity: 0,
      stagger: 0.15,
      duration: 0.8,
      ease: "power3.out"
    });
  }
}

/* ──────────────────────────────────────────────────────────────
   9. Scroll Storytelling (Pinned 3 Steps)
   ────────────────────────────────────────────────────────────── */
function initScrollStorytelling() {
  if (!window.gsap || !window.ScrollTrigger) return;

  const steps = document.querySelectorAll(".story-step-card");
  if (!steps.length) return;

  steps.forEach((step, index) => {
    ScrollTrigger.create({
      trigger: step,
      start: "top center",
      end: "bottom center",
      onEnter: () => activateStep(index),
      onEnterBack: () => activateStep(index)
    });
  });

  function activateStep(idx) {
    steps.forEach((s, i) => {
      s.classList.toggle("active-step", i === idx);
    });

    const previewScreen = document.getElementById("story-preview-screen");
    if (previewScreen) {
      const stepLabels = [
        "Phase 1: Continuous High-Frequency Telemetry Ingestion (54 Features)",
        "Phase 2: Local Isolation Forest Anomaly Isolation (<0.01ms)",
        "Phase 3: Automated Deduplication, Cooldown & Triage Alert Dispatch"
      ];
      previewScreen.textContent = stepLabels[idx] || "";
    }
  }
}

/* ──────────────────────────────────────────────────────────────
   10. Horizontal Scroll Showcase Gallery
   ────────────────────────────────────────────────────────────── */
function initHorizontalShowcase() {
  if (!window.gsap || !window.ScrollTrigger) return;

  const track = document.getElementById("gallery-track");
  const section = document.querySelector(".gallery-section");

  if (!track || !section) return;

  const totalWidth = track.scrollWidth - window.innerWidth + 100;

  if (totalWidth > 0 && window.innerWidth > 768) {
    gsap.to(track, {
      x: -totalWidth,
      ease: "none",
      scrollTrigger: {
        trigger: section,
        pin: true,
        scrub: 1,
        start: "top top",
        end: () => `+=${totalWidth}`
      }
    });
  }
}

/* ──────────────────────────────────────────────────────────────
   11. Pricing Toggle (Monthly / Annual Flip)
   ────────────────────────────────────────────────────────────── */
function initPricingToggle() {
  const switchBtn = document.getElementById("pricing-switch-btn");
  if (!switchBtn) return;

  let isAnnual = false;
  const priceElements = document.querySelectorAll(".price-value[data-monthly]");

  switchBtn.addEventListener("click", () => {
    isAnnual = !isAnnual;
    switchBtn.classList.toggle("annual", isAnnual);

    priceElements.forEach(el => {
      const monthly = el.getAttribute("data-monthly");
      const annual = el.getAttribute("data-annual");
      const targetVal = isAnnual ? annual : monthly;

      if (window.gsap) {
        gsap.to(el, {
          scale: 0.8,
          opacity: 0,
          duration: 0.15,
          onComplete: () => {
            el.textContent = targetVal;
            gsap.to(el, { scale: 1, opacity: 1, duration: 0.25 });
          }
        });
      } else {
        el.textContent = targetVal;
      }
    });
  });
}

/* ──────────────────────────────────────────────────────────────
   12. Testimonials Carousel
   ────────────────────────────────────────────────────────────── */
function initTestimonialsCarousel() {
  const track = document.getElementById("testimonials-track");
  if (!track) return;

  let currentIdx = 0;
  const cards = track.querySelectorAll(".testimonial-card");
  if (cards.length <= 1) return;

  function slideTo(idx) {
    currentIdx = idx % cards.length;
    const cardWidth = cards[0].offsetWidth + 32;
    track.style.transform = `translateX(-${currentIdx * cardWidth}px)`;
  }

  // Auto play every 4 seconds
  let timer = setInterval(() => {
    slideTo(currentIdx + 1);
  }, 4000);

  track.addEventListener("mouseenter", () => clearInterval(timer));
  track.addEventListener("mouseleave", () => {
    timer = setInterval(() => slideTo(currentIdx + 1), 4000);
  });
}

/* ──────────────────────────────────────────────────────────────
   13. FAQ Accordion
   ────────────────────────────────────────────────────────────── */
function initFaqAccordion() {
  const items = document.querySelectorAll(".faq-item");
  items.forEach(item => {
    const trigger = item.querySelector(".faq-trigger");
    trigger.addEventListener("click", () => {
      const isOpen = item.classList.contains("open");
      items.forEach(i => i.classList.remove("open"));
      if (!isOpen) item.classList.add("open");
    });
  });
}
