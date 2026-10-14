# Craft Apps — complete ArtCraft suite

This is an independent community fork of [LinuxServer.io's Craft Apps container](https://github.com/linuxserver/docker-craft-apps). It retains the LinuxServer Ubuntu/Selkies browser-accessible desktop and adds the rest of the [official ArtCraft app lineup](https://getartcraft.com/apps).

The original container bundles seven apps: PhotoCraft, VectorCraft, FilmCraft, LightCraft, PdfCraft, EffectCraft and DesignCraft. This fork also includes **FigCraft, WordCraft, SoundCraft, DeckCraft, CADCraft and GridCraft**, bringing the suite to **13 apps**:

__CRAFT_APPS__

The table above is maintained automatically from the verified release inventory. Compatible new apps from the official catalog are also added to the installation, desktop shortcuts and menus.

## Use this fork

```bash
docker pull ghcr.io/timminater/docker-craft-apps:latest
docker run -d \
  --name craft-apps \
  --shm-size=1g \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Europe/Amsterdam \
  -p 3001:3001 \
  -v /path/to/craft-apps/config:/config \
  --restart unless-stopped \
  ghcr.io/timminater/docker-craft-apps:latest
```

Open `https://yourhost:3001/`. Choose the host config directory and user/group IDs for your system. The desktop has no authentication by default; use it on a trusted network or configure authentication as described below.

`latest` automatically selects **linux/amd64** or **linux/arm64**. Architecture-specific aliases are `amd64-latest` and `arm64v8-latest`. Each successful run also publishes an immutable `build-<run-id>-<attempt>` tag for rollback.

## Automatic builds and updates

[GitHub Actions](https://github.com/Timminater/docker-craft-apps/actions/workflows/publish-ghcr.yml) checks the official app catalog and the latest stable GitHub releases, commits any compatible app/version changes, and builds both architectures. This runs on relevant `master` changes, manually through **Run workflow**, and **every Monday at 03:17 UTC** (04:17 in Dutch winter time / 05:17 in summer time). Weekly builds also refresh the base image.

Both images use the same [release inventory](root/defaults/craft-releases.json). Installed versions, desktop startup and restart with an existing config are checked before publication. The multi-architecture `latest` tag is updated only if both architectures pass. These checks do not exercise every feature inside each Craft application. Incompatible new packaging or failed builds require review and leave the previously published `latest` image available.

To receive new apps/releases on your host, pull the new image and recreate your container while retaining the `/config` volume. Restarting the existing container alone does not install updates.

The instructions below originate from LinuxServer.io and describe the inherited desktop platform. **Support for this fork and its additional apps is independent of LinuxServer.io.**

---

