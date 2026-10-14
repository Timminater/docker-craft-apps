# syntax=docker/dockerfile:1

FROM ghcr.io/linuxserver/baseimage-selkies:ubunturesolute

# set version label
ARG BUILD_DATE
ARG VERSION
ARG PHOTOCRAFT_RELEASE
ARG CRAFT_RELEASES
LABEL build_version="Linuxserver.io version:- ${VERSION} Build-date:- ${BUILD_DATE}"
LABEL maintainer="thelamer"

# title
ENV TITLE="Craft Apps" \
    NO_FULL=true \
    SELKIES_DESKTOP=true \
    PIXELFLUX_WAYLAND=true

RUN \
  echo "**** add icon ****" && \
  curl -o \
    /usr/share/selkies/www/icon.png \
    https://raw.githubusercontent.com/linuxserver/docker-templates/master/linuxserver.io/img/artcraft-logo.png && \
  echo "**** install packages ****" && \
  add-apt-repository ppa:xtradeb/apps && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
    caja \
    chromium \
    chromium-l10n \
    libegl1 \
    xdg-desktop-portal \
    xdg-desktop-portal-gtk && \
  echo "**** install photocraft ****" && \
  if [ -z ${PHOTOCRAFT_RELEASE+x} ]; then \
    if [ -n "${CRAFT_RELEASES:-}" ]; then \
      PHOTOCRAFT_RELEASE=$(printf '%s' "${CRAFT_RELEASES}" | jq -er '.photocraft') || exit 1; \
    else \
      PHOTOCRAFT_RELEASE=$(curl -fsSL "https://api.github.com/repos/storytold/photocraft/releases/latest" \
        | jq -er '.tag_name | select(type == "string" and length > 0)') || exit 1; \
    fi; \
  fi && \
  curl -f -o \
    /tmp/photocraft.deb -L \
    "https://github.com/storytold/photocraft/releases/download/${PHOTOCRAFT_RELEASE}/photocraft-$(echo ${PHOTOCRAFT_RELEASE} | sed 's/^v//g')-linux-x86_64.deb" && \
  echo "**** install craft suite ****" && \
  for APP in cadcraft deckcraft designcraft effectcraft figcraft filmcraft gridcraft lightcraft pdfcraft soundcraft vectorcraft wordcraft; do \
    if [ -n "${CRAFT_RELEASES:-}" ]; then \
      APP_RELEASE=$(printf '%s' "${CRAFT_RELEASES}" | jq -er --arg app "${APP}" '.[$app]') || exit 1; \
    else \
      APP_RELEASE=$(curl -fsSL "https://api.github.com/repos/storytold/${APP}/releases/latest" \
        | jq -er '.tag_name | select(type == "string" and length > 0)') || exit 1; \
    fi && \
    curl -f -o \
      /tmp/${APP}.deb -L \
      "https://github.com/storytold/${APP}/releases/download/${APP_RELEASE}/${APP}-$(echo ${APP_RELEASE} | sed 's/^v//g')-linux-x86_64.deb" || exit 1; \
  done && \
  apt-get install -y --no-install-recommends \
    /tmp/*.deb && \
  echo "**** application tweaks ****" && \
  mv \
    /usr/bin/chromium \
    /usr/bin/chromium-real && \
  sed -i \
    's/^Icon=.*/Icon=system-file-manager-symbolic/' \
    /usr/share/applications/caja.desktop && \
  echo "**** cleanup ****" && \
  apt-get autoclean && \
  rm -rf \
    /config/.cache \
    /tmp/* \
    /usr/share/applications/caja-autorun-software.desktop \
    /usr/share/applications/caja-browser.desktop \
    /usr/share/applications/caja-computer.desktop \
    /usr/share/applications/caja-file-management-properties.desktop \
    /usr/share/applications/caja-folder-handler.desktop \
    /usr/share/applications/caja-home.desktop \
    /usr/share/applications/debian-uxterm.desktop \
    /usr/share/applications/debian-xterm.desktop \
    /usr/share/applications/footclient.desktop \
    /usr/share/applications/foot-server.desktop \
    /usr/share/applications/mate-about.desktop \
    /usr/share/applications/mate-color-select.desktop \
    /usr/share/applications/mate-network-scheme.desktop \
    /usr/share/applications/st.desktop \
    /var/lib/apt/lists/* \
    /var/tmp/*

# add local files
COPY /root /

# ports and volumes
EXPOSE 3001

VOLUME /config
