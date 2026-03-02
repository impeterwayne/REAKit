# Muslim Pro — Decompiled APK Project Overview

> **Project Type:** Decompiled Android Application (Reverse Engineering Target)
> **Package:** `com.bitsmedia.android.muslimpro`
> **Version:** 17.0.4 (versionCode: 1700040401)
> **Platform:** Android (minSdk 24, targetSdk 35, compileSdk 35)
> **Decompiler Output:** JADX-style Java source reconstruction
> **Date Scanned:** 2026-02-28

---

## Executive Summary

This project is the **decompiled source** of **Muslim Pro**, a comprehensive Islamic lifestyle Android application published by **Bitsmedia**. The decompilation was performed using an APK decompiler (likely JADX or apktool+dex2jar), producing ~58,781 Java source files across the app module.

Muslim Pro is a large-scale production app with **104 feature modules**, extensive 3rd-party SDK integrations (ads, analytics, payments, social), and a modern Android tech stack using Kotlin (compiled to Java), Jetpack Compose, Retrofit2/OkHttp3, and Dagger/Hilt dependency injection.

---

## Technology Stack

| Category | Technology | Details |
|---|---|---|
| **Language** | Java / Kotlin (decompiled) | Kotlin metadata preserved in annotations |
| **Platform** | Android SDK 35 | minSdk 24, targetSdk 35 |
| **UI Framework** | Jetpack Compose + XML Views | Material Design 3 components, legacy XML layouts |
| **Networking** | Retrofit2 + OkHttp3 | REST API clients with custom interceptors |
| **DI Framework** | Dagger / Hilt | `@Module`, `@Component`, `@Inject` patterns |
| **Serialization** | Moshi + Kotlinx Serialization | JSON adapters, `@Metadata` annotations |
| **Image Loading** | Coil3 + Glide (Bumptech) | Modern image pipeline |
| **Database** | Room / SQLite | Local data persistence |
| **Analytics** | Firebase Analytics, Adjust, Facebook SDK, TikTok SDK | Multi-platform attribution |
| **Ads** | Google AdMob/Ad Manager, AppLovin, Vungle, ByteDance/Pangle | Mediation stack |
| **Payments** | Google Play Billing, Samsung IAP, Alipay | Multi-store billing |
| **Auth** | Firebase Auth | Email, social login |
| **Push** | Firebase Cloud Messaging (FCM) | C2D/GCM legacy compat |
| **Support** | Zendesk | Customer support SDK |
| **Media** | ExoPlayer / MediaPlayer | Audio playback (Quran recitation, Adhan) |
| **Maps** | Google Maps, Google Places | Halal places, Qibla direction |
| **Deep Linking** | OneLink, muslimpro:// scheme | 30+ custom URI handlers |

---

## Application Features (by Module)

The app contains **104 feature modules** organized under `com.bitsmedia.android.*`:

### Core Religious Features
- **prayer** (92 files) — Prayer times, calculation methods, notifications, widgets
- **quran** (558 files) — Full Quran reader, audio recitation, search, bookmarks, khatam
- **qibla** (7 files) — Compass-based Qibla direction finder
- **dua** (33 files) — Supplication/Dua collection with audio
- **tasbih** (34 files) — Digital tasbeeh counter
- **names** (7 files) — 99 Names of Allah
- **calendar** (17 files) — Islamic/Hijri calendar with holidays
- **adhan** (1 file) — Call to prayer audio
- **fasting** (11 files) — Ramadan fasting tracker
- **zakat** (32 files) — Zakat calculator

### Content & Media
- **quranlesson** (16 files) — Quran learning courses
- **quranmemorization** (22 files) — Memorization tools
- **quransearch** (37 files) — Advanced Quran search
- **inspiration** (87 files) — Daily inspirational content
- **dailydeen** (25 files) — Daily Islamic content feed
- **story** (32 files) — Story/article content system
- **deenmode** (51 files) — Focused Islamic mode

### Video & Streaming
- **qalboxdata** (212 files) — Qalbox video platform data layer
- **qalboxmobile** (123 files) — Qalbox mobile video player UI
- **meccalive** (6 files) — Live Mecca stream
- **casting** (6 files) — Chromecast/media casting
- **customplayer** (11 files) — Custom media player
- **mediaplayer** (4 files) — Media playback controller

### Social & Community
- **community** (182 files) — Community/Ummah social features
- **journal** (84 files) — Personal journal/diary
- **gamification** (106 files) — Achievements, streaks, badges
- **profile** (19 files) — User profile management
- **share** (5 files) — Social sharing utilities

### Commerce & Premium
- **premium** (62 files) — Premium subscription features
- **purchase** (16 files) — In-app purchase logic
- **freetrial** (20 files) — Free trial management
- **marketplace** (15 files) — Digital marketplace
- **nps** (16 files) — Net Promoter Score surveys

### Places & Travel
- **halalplaces** (3 files) — Halal restaurant finder
- **halalplacesdetail** (5 files) — Place detail views
- **places** (50 files) — Places discovery
- **hajjjourney** (24 files) — Hajj journey guide
- **hajjumrah** (14 files) — Hajj/Umrah tools
- **umrahme** (17 files) — Umrah booking integration

### Infrastructure
- **api** (19 files) — REST API client layer
- **base** (153 files) — Base classes, utilities
- **core** (40 files) — Core application logic
- **config** (19 files) — Remote config, feature flags
- **authentication** (51 files) — Auth flows
- **analytics** (3 files) — Analytics abstraction layer
- **ads** (39 files) — Ad mediation/loading
- **notification** (2 files) — Push notification handling
- **location** (35 files) — Location services
- **syncmanager** (13 files) — Data sync engine
- **widget** (48 files) — Home screen widgets

---

## Architecture Pattern

The app follows a **multi-module MVVM (Model-View-ViewModel)** architecture with:

- **Clean Architecture layers**: data → domain → presentation
- **Dependency Injection** via Dagger/Hilt modules
- **Repository pattern** for data access
- **Reactive streams** (Kotlin Coroutines/Flow via decompiled patterns)
- **Jetpack Compose** for modern UI alongside legacy XML views

---

## Deep Link Scheme

The app registers the custom scheme `muslimpro://` with 30+ host handlers:
`qalbox`, `academy`, `hajjumrah`, `makkah`, `article`, `virtual_tour`, `tasbih`, `freetrial`, `image`, `video`, `qibla`, `timeline`, `more`, `shahadah`, `calendar`, `prayers`, `login`, `zakat`, `inspiration`, `content`, `tracker`, `quran`, `playlist`, `message`, `khatam`, `names`, `duas`, `ummah`, `premium`, `deen-mode`, `umrah`, `halal`, `story`, `colortheme`, `athanpreferences`, `quranthemes`, `quranarabictext`, `quranaudio`, `blog`, `dailydeen`, `myfreetrial`, `quran-learn`, `quran-lesson`, `quran-me`, `quran-memorise`, `quran-immerse`, `quran-discover`, `quran-search`, `quran-sura`, `quran-resource`

HTTPS deep links:
- `muslimpro-bitsmedia.onelink.me`
- `muslimpro.go.link`
- `go.qalbox.com`
- `www.qalbox.com`
- `www.muslimpro.com/app/`, `www.muslimpro.com/qalbox/`

---

## Reverse Engineering Notes

### Decompilation Artifacts
- **Obfuscated packages**: `defpackage/` (17,135 files), `p310e/`, `p312j$/` — ProGuard/R8 obfuscated
- **Renamed classes**: `C0xxx`, `AbstractC0xxx`, `EnumC0xxx`, `InterfaceC0xxx` patterns
- **Generated code**: `R.java` (1.38 MB), `DataBinderMapperImpl.java` files
- **Library code**: Full source of `androidx.*`, `com.google.*`, `com.facebook.*`, `okhttp3.*`, `retrofit2.*`, `zendesk.*` libraries included

### Key Entry Points
- **Application class**: `com.bitsmedia.android.muslimpro.core.MPApplication`
- **Splash Activity**: `com.bitsmedia.android.muslimpro.core.activities.SplashActivity` (LAUNCHER)
- **Network Module**: `com.bitsmedia.android.qalboxdata.data.p074di.QalboxNetworkModule`
- **API Layer**: `com.bitsmedia.android.api.*`

### APK Split Configuration
- **Base APK**: Main code + resources
- **ABI splits**: `arm64_v8a`, `armeabi_v7a`, `x86`, `x86_64`
- **Density splits**: `hdpi`, `mdpi`, `xhdpi`, `xxhdpi`, `xxxhdpi`, etc.
- **DEX files**: 9 dex files (classes.dex through classes9.dex, ~102MB total)
