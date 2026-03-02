# Muslim Pro — Architecture Document

> **Source:** Decompiled APK (JADX output)
> **Package:** `com.bitsmedia.android.muslimpro`
> **Architecture:** Multi-module MVVM + Clean Architecture

---

## 1. High-Level Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     Android Application                     │
│                  (MPApplication : Application)              │
├─────────────┬──────────────┬──────────────┬────────────────┤
│  Presentation│    Domain    │    Data      │    Framework   │
│  (UI Layer)  │  (Business)  │  (Repository)│   (Platform)   │
├─────────────┼──────────────┼──────────────┼────────────────┤
│ Activities   │ UseCases     │ Repositories │ Firebase       │
│ Fragments    │ ViewModels   │ API Services │ Google Play    │
│ Compose UI   │ Mappers      │ DAOs         │ Location       │
│ Adapters     │ Models       │ DTOs         │ Notifications  │
│ Widgets      │              │ SharedPrefs  │ Media Player   │
└─────────────┴──────────────┴──────────────┴────────────────┘
```

## 2. Dependency Injection (Dagger/Hilt)

### Module Structure
The DI graph is organized through several key modules:

| Module | Location | Responsibility |
|---|---|---|
| `QalboxNetworkModule` | `qalboxdata.data.p074di` | Retrofit/OkHttp setup for Qalbox API |
| Root DI (`p058di`, `p038di`) | `muslimpro.p058di`, `android.p038di` | App-level singleton bindings |
| Feature-level modules | Per-feature `di` packages | Feature-scoped dependencies |

### DI Graph Flow
```
AppComponent (Singleton)
├── NetworkModule → Retrofit → OkHttpClient → Interceptors
├── DatabaseModule → Room Database → DAOs
├── RepositoryModule → Repositories → API + DB
└── Feature Modules
    ├── QalboxNetworkModule
    ├── PrayerModule 
    ├── QuranModule
    └── ... (per feature)
```

## 3. Networking Architecture

### Stack
```
Application Code
    ↓
Retrofit2 Interface (annotated service)
    ↓
OkHttp3 Client
    ├── Custom Interceptors (auth, logging, headers)
    ├── NetworkInterceptor
    └── CookieJar
    ↓
HTTP/HTTPS → Backend API
```

### Key API Layers

#### Core API (`com.bitsmedia.android.api`)
- `adapter/` — 7 files: Custom Retrofit type adapters
- `model/` — 5 files: Core API request/response models
- `p024di/` — 2 files: DI module for network setup
- `response/` — 4 files: Common API response wrappers

#### Qalbox Video API (`com.bitsmedia.android.qalboxdata.data`)
- `p074di/` — 5 files: **QalboxNetworkModule** — Primary network configuration
- `model/` — 203 files: Extensive video/content DTOs and domain models
- `utils/` — 2 files: API utility helpers

### API Domains (from deep links & manifest)
- `muslimpro-bitsmedia.onelink.me` — Attribution deep links
- `go.qalbox.com` / `www.qalbox.com` — Qalbox video platform
- `www.muslimpro.com` — Main web platform

## 4. Data Layer Architecture

### Local Storage
- **Room Database** — Structured data (prayers, bookmarks, quran progress)
- **SharedPreferences** — Settings, feature flags, user preferences
- **File Storage** — Downloaded audio (Quran recitations, Adhan tones)
- **Cache** — OkHttp disk cache, Coil/Glide image cache

### Data Models
Key model packages:
- `model/` (70 files at root) — Core business models
- `qalboxdata.model/` (203 files) — Qalbox video content models
- `inspiration.data.model/` — Content/article models
- `story.data.remote/` — Story DTOs
- `community/` (182 files) — Social/community models

### Serialization
- **Moshi** (`com.squareup.moshi`) — JSON parsing with adapters
- **Kotlinx Serialization** — Kotlin serialization with `@Serializable` 
- **Parcelable** — Android IPC data transfer

## 5. UI Architecture

### Dual UI System
The app uses both legacy and modern UI frameworks:

1. **Jetpack Compose** (Material Design 3)
   - Compose UI components in `defpackage/` (decompiled compose runtime)
   - Material3 theming, colors, shapes
   - `composeui/`, `designsystem/` packages

2. **XML Views** (Legacy)
   - Fragment-based navigation
   - RecyclerView + Adapters
   - Custom views in `commonui/` (58 files), `sharedui/` (17 files)
   - ViewBinding (`databinding/` — 48 files)

### Navigation
- **Deep Link handlers** — 30+ URI schemes handled in SplashActivity
- **Intent-based navigation** — Activity-to-Activity
- **Fragment-based** — Fragment transactions within Activities

## 6. Third-Party SDK Integration

### Advertising Stack
| SDK | Package | Purpose |
|---|---|---|
| Google AdMob/GAM | `com.google.android.gms.ads` | Primary ad serving |
| AppLovin | `com.applovin` | Mediation network |
| Vungle | `com.vungle` | Video ads |
| ByteDance/Pangle | `com.bytedance` | TikTok Audience Network |
| Facebook Audience Network | `com.facebook.ads` | Social ads |
| IMA SDK | `com.google.ads.interactivemedia` | Video pre-roll ads |

### Analytics & Attribution
| SDK | Package | Purpose |
|---|---|---|
| Firebase Analytics | `com.google.firebase.analytics` | Event tracking |
| Adjust | `com.adjust` | Attribution |
| Facebook SDK | `com.facebook` | Social analytics |
| TikTok SDK | `com.tiktok` / `com.bytedance` | TikTok attribution |
| APM | `com.apm` | Performance monitoring |

### Payments
| SDK | Package | Purpose |
|---|---|---|
| Google Play Billing | `com.android.vending.billing` | IAP |
| Samsung IAP | `com.samsung.android.iap` | Samsung Store |
| Alipay | `com.alipay` | China payments |
| IAB | `com.iab` | In-app billing abstraction |
| Purchasely | `com.bitsmedia.android.purchasely` | Subscription management |

### Support & CRM
| SDK | Package | Purpose |
|---|---|---|
| Zendesk | `zendesk.*` | Customer support tickets |
| Firebase Auth | `com.google.firebase.auth` | Authentication |

## 7. App Initialization Flow

```
1. MPApplication.onCreate()
   ├── AndroidX Startup Initializers:
   │   ├── AdjustInitializer (attribution)
   │   ├── AdjustAdidInitializer (ad ID) 
   │   ├── CrashlyticsInitializer (crash reporting)
   │   ├── ConfigInitializer (remote config)
   │   ├── FacebookInitializer (FB SDK)
   │   ├── ComposeTracingInitializer (perf tracing)
   │   ├── EmojiCompatInitializer (emoji support)
   │   ├── ProcessLifecycleInitializer
   │   ├── ProfileInstallerInitializer
   │   └── JodaTimeInitializer (date/time)
   │
2. SplashActivity (LAUNCHER)
   ├── Deep link parsing (30+ URI handlers)
   ├── Permission checks
   ├── Auth state check
   └── → Main Activity / Onboarding

3. Main Experience
   ├── Today tab (66 files)
   ├── Timeline (59 + 23 files)
   ├── Prayer times
   ├── Quran reader
   └── More/Settings
```

## 8. Security Considerations

### Permissions (from AndroidManifest)
- `INTERNET`, `ACCESS_NETWORK_STATE`, `ACCESS_WIFI_STATE`
- `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`
- `CAMERA`, `RECORD_AUDIO`
- `WRITE_EXTERNAL_STORAGE`, `READ_EXTERNAL_STORAGE`
- `VIBRATE`, `WAKE_LOCK`
- `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_MEDIA_PLAYBACK`
- `RECEIVE_BOOT_COMPLETED`
- `POST_NOTIFICATIONS`, `USE_EXACT_ALARM`
- `SYSTEM_ALERT_WINDOW`

### Protection
- **ProGuard/R8 obfuscation** applied (many classes renamed)
- **Network security config** referenced (`@xml/network_security_config`)
- **Play Integrity** (`com.pairip`, `com.google.android.play.integrity`)
- **pairip protection** (`com.pairip.*` — 3 files) — Anti-tampering
