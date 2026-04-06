# GitHub Push Commands

## First time setup (run once)
```bash
cd C:\Users\Speedy\Desktop\Scumbagclips\ClipfinderBETA
git init
git remote add origin https://github.com/thatspeedykid/clipfinder.git
git branch -M main
```

## Push initial 1.0 release
```bash
git add .
git commit -m "feat: ClipFinder v1.0 initial release"
git push -u origin main

# Tag as v1.0 (triggers GitHub Actions build)
git tag v1.0
git push origin v1.0
```

## For v1.1 (when ready)
```bash
git add .
git commit -m "feat: ClipFinder v1.1 - hybrid clip detection + bug fixes"
git tag v1.1
git push origin main --tags
```

## Files to include in repo root
- clipfinder.py
- clipfinder.ico
- setup_build.py
- make_installer.bat
- installer.nsi
- README.md
- CHANGELOG.md
- requirements.txt
- .gitignore
- .github/workflows/build.yml
- assets/logo.png
- assets/preview.webp
