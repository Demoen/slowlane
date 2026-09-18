---
title: Apple automation. At your pace.
description: A focused Python CLI for App Store Connect, code signing, TestFlight, and macOS uploads. Take the scenic route to your next release.
hide:
  - navigation
  - toc
  - feedback
---

<div class="sl-home" id="__skip" tabindex="-1">
  <section class="sl-hero" aria-labelledby="hero-title">
    <div class="sl-hero__art" aria-hidden="true">
      <img class="sl-shell" src="assets/shell.svg" alt="" width="860" height="860">
      <div class="sl-snail"><span>🐌</span></div>
      <span class="sl-orbit-label">steady by design</span>
    </div>
    <div class="sl-hero__copy">
      <p class="sl-eyebrow"><span></span> SMALL CLI. BIG RELEASE ENERGY.</p>
      <h1 id="hero-title">Apple automation.<br><em>At your pace.</em></h1>
      <p class="sl-hero__description">Your apps, builds, and signing workflows.<br>One thoughtful Python CLI. Take the scenic<br class="sl-desktop-break"> route to your next release.</p>
      <div class="sl-actions">
        <a class="sl-button sl-button--primary" href="installation/">Get started <span aria-hidden="true">↗</span></a>
        <a class="sl-button sl-button--secondary" href="cli/">Explore the CLI <span aria-hidden="true">→</span></a>
      </div>
      <p class="sl-hero__footnote">Open source · Python 3.14+ · Built on Apple’s public APIs</p>
    </div>
    <div class="sl-hero__bottom"><span>LESS CEREMONY. MORE SHIPPING.</span><a href="#take-the-first-step">Scroll to explore <span aria-hidden="true">↓</span></a></div>
  </section>

  <section class="sl-start" aria-labelledby="take-the-first-step">
    <div>
      <p class="sl-eyebrow">01 / A LITTLE MOMENTUM</p>
      <h2 id="take-the-first-step">Start small.<br>Keep moving.</h2>
      <p>Install Slowlane, connect an API key, and see your apps. The same commands fit your terminal and your CI pipeline.</p>
      <a class="sl-text-link" href="authentication/">Connect your Apple API key <span aria-hidden="true">↗</span></a>
    </div>
    <div class="sl-terminal">
      <div class="sl-terminal__bar"><span aria-hidden="true">● ● ●</span><span>your next release starts here</span></div>
      <div class="sl-terminal__body"><pre><code><span class="sl-prompt">$</span> python -m pip install slowlane

<span class="sl-terminal__muted"># After configuring your API key</span>
<span class="sl-prompt">$</span> slowlane doctor
<span class="sl-prompt">$</span> slowlane asc apps list
<span class="sl-prompt">$</span> slowlane --json asc builds list</code></pre></div>
      <div class="sl-terminal__footer"><span>API keys in. Useful output out.</span><a href="configuration/">Configuration →</a></div>
    </div>
  </section>

  <section class="sl-workflows" aria-labelledby="a-place-for-every-step">
    <div class="sl-section-heading"><div><p class="sl-eyebrow">02 / YOUR RELEASE TOOLKIT</p><h2 id="a-place-for-every-step">A place for every step.</h2></div><p>Focused commands for the work<br>between an idea and a release.</p></div>
    <div class="sl-cards">
      <a class="sl-card" href="usage/apps/"><span class="sl-card__number">01 <span aria-hidden="true">↗</span></span><h3>Know your apps.</h3><p>Find app records, inspect metadata, and use resource IDs in the rest of your workflow.</p><code>slowlane asc apps list</code></a>
      <a class="sl-card" href="usage/builds/"><span class="sl-card__number">02 <span aria-hidden="true">↗</span></span><h3>Meet your next build.</h3><p>Find builds and bring testers into the loop with TestFlight groups and invitations.</p><code>slowlane asc builds latest APP_ID</code></a>
      <a class="sl-card" href="usage/profiles/"><span class="sl-card__number">03 <span aria-hidden="true">↗</span></span><h3>Sign with intention.</h3><p>Manage certificates and profiles with a team API key and explicit certificate selection.</p><code>slowlane signing profiles list</code></a>
      <a class="sl-card" href="usage/upload/"><span class="sl-card__number">04 <span aria-hidden="true">↗</span></span><h3>Send it on its way.</h3><p>Validate and upload signed IPA and PKG artifacts with Apple’s tools on macOS.</p><code>slowlane upload ipa ./App.ipa</code></a>
    </div>
  </section>

  <section class="sl-outro" aria-labelledby="a-few-good-boundaries">
    <div><p class="sl-eyebrow">03 / A FEW GOOD BOUNDARIES</p><h2 id="a-few-good-boundaries">Clear about what’s inside.</h2><p>Public API authentication. JSON for automation. Signing with team keys. Uploads on macOS. Start with the requirements for your workflow, then make it your own.</p><div class="sl-outro__links"><a href="installation/">Requirements ↗</a><a href="migration/">Moving from 0.3? ↗</a><a href="https://github.com/Demoen/slowlane">View on GitHub ↗</a></div></div>
    <span class="sl-outro__snail" aria-hidden="true">🐌</span>
  </section>
</div>
