# Thomas's Toothbrush Timer 🦷🪥

A fun, kid-friendly toothbrushing app that runs in the browser — made for the iPad.

It runs a **2-minute timer** split into the four quadrants of the mouth (30 seconds each, following dental guidance), with a cartoon mouth and an animated toothbrush showing exactly which teeth to brush. Within each quadrant it cycles through **outside → inside → chewing tops**, cheerful chimes mark each switch, and finishing earns a confetti celebration.

The mouth is shown **mirror-style**: "Top Right" lights up on the right side of the screen, matching the child's own right, just like looking in a bathroom mirror.

## Features

- ⏱️ Accurate 2-minute countdown with a progress ring
- 🦷 Four-quadrant cartoon mouth with an animated scrubbing toothbrush
- 🔊 Gentle chimes when it's time to move on, fanfare at the end (mute button included, remembered between visits)
- ⭐ Stars for each finished quadrant and a confetti "All clean!" screen
- ⏸️ Tap anywhere to pause (with start-over and back-to-start options)
- 📱 Keeps the iPad screen awake while brushing (on iPadOS versions that support it)
- 📦 One self-contained HTML file — no installs, no internet needed after loading

## Setting it up (one time)

1. **Merge this branch into `main`** (open and merge the pull request, or merge locally).
2. In this repo on GitHub, go to **Settings → Pages**, and under *Build and deployment* choose **Deploy from a branch**, branch **`main`**, folder **`/ (root)`**. Save.
3. After a minute or two the app will be live at:

   **https://adamskate123.github.io/thomastoothbrush/**

## Putting it on the iPad

1. Open the link above in **Safari** on the iPad.
2. Tap the **Share** button (the square with the up arrow).
3. Tap **Add to Home Screen**, then **Add**.

You'll get a cute tooth icon on the home screen, and the app opens full-screen like a real app.

## For grown-ups: testing tip

Add `?speed=10` to the URL (e.g. `index.html?speed=10`) to make the 2 minutes run 10× faster while you check it out.
