# Muslim Pro — Source Tree Analysis

> **Root:** `d:\Quest\Product_RE_Tools\decoded`
> **Total Files:** ~58,781

---

## Top-Level Structure

```
decoded/
├── build.gradle                    # Root Gradle build (AGP 8.10.1)
├── settings.gradle                 # Root project name: 'UNKNOWN'
└── app/
    ├── build.gradle                # App module (com.bitsmedia.android.muslimpro)
    └── src/
        └── main/
            ├── com.bitsmedia.android.muslimpro.apk/   # Extracted APK contents
            │   ├── AndroidManifest.xml                # 3,792 lines — full manifest
            │   ├── assets/                            # 76 asset files
            │   ├── res/                               # 1,479 resource entries
            │   ├── META-INF/                          # 179 signing/metadata files
            │   ├── classes.dex — classes9.dex          # 9 DEX files (~102MB)
            │   ├── kotlin/                            # Kotlin metadata
            │   ├── *.properties                       # ~40 library property files
            │   └── *.proto                            # Protobuf schemas
            ├── config.*.apk/                          # ABI/density split APKs
            │   ├── config.arm64_v8a.apk/
            │   ├── config.armeabi_v7a.apk/            # 17 native lib entries
            │   ├── config.x86.apk/                    # 10 entries
            │   ├── config.x86_64.apk/                 # 10 entries
            │   └── config.{hdpi,mdpi,xhdpi,...}.apk/  # ~348 density resources each
            ├── java/                                   # ★ DECOMPILED JAVA SOURCE
            │   ├── com/bitsmedia/android/             # ★ APP SOURCE (3,183 files)
            │   │   └── [104 feature packages]
            │   ├── defpackage/                         # Obfuscated classes (17,135)
            │   ├── com/google/                         # Google libs (12,458)
            │   ├── androidx/                           # AndroidX libs (14,900)
            │   ├── com/facebook/                       # Facebook SDK (2,441)
            │   ├── com/bytedance/                      # ByteDance/TikTok (1,272)
            │   ├── zendesk/                            # Zendesk SDK (531)
            │   ├── io/                                 # IO libraries (483)
            │   ├── org/                                # Apache/other (343)
            │   ├── p310e/                              # Obfuscated pkg (284)
            │   ├── com/applovin/                       # AppLovin SDK (125)
            │   ├── okhttp3/                            # OkHttp3 (132)
            │   ├── com/bykv/                           # ByteView (131)
            │   ├── com/iap/                            # IAP library (133)
            │   ├── com/apm/                            # APM (93)
            │   ├── p312j$/                             # Obfuscated (83)
            │   ├── com/adjust/                         # Adjust SDK (79)
            │   ├── com/vungle/                         # Vungle (60)
            │   ├── kotlin/                             # Kotlin stdlib (57)
            │   ├── com/iab/                            # IAB (44)
            │   ├── com/alipay/                         # Alipay (41)
            │   ├── com/pgl/                            # PGL library (37)
            │   ├── kotlinx/                            # Kotlinx (32)
            │   ├── com/android/                        # Android compat (25)
            │   ├── android/                            # System stubs (12)
            │   ├── com/squareup/                       # Square libs (13)
            │   ├── me/                                 # Me.* libraries (7)
            │   ├── net/                                # Net libraries (4)
            │   ├── com/pairip/                         # Anti-tampering (3)
            │   ├── dagger/                             # Dagger core (3)
            │   ├── javax/                              # Javax inject (3)
            │   ├── coil3/                              # Coil3 image (3)
            │   └── retrofit2/                          # Retrofit2 (1)
            └── res/                                    # Merged resources
                ├── values/                             # 12 base value files
                └── values-{locale}/                    # 73 localized variants
                    ├── ar, az, bn, da, de, en, es, ff
                    ├── fr, hi, in, it, ja, ms, nl
                    ├── pt, ru, th, tr, ug, ur, zh, zh-rCN
                    └── ... (density/dimension variants)
```

---

## Critical Directories

### ★ App Source Code (`com/bitsmedia/android/`)
**3,183 files across 104 feature modules — PRIMARY ANALYSIS TARGET**

```
com/bitsmedia/android/
├── api/                  (19)  # REST API client layer
├── authentication/       (51)  # Auth flows (Firebase Auth)
├── base/                (153)  # Base classes, utilities, helpers
├── core/                 (40)  # Core app logic, MPApplication
├── config/               (19)  # Remote config, feature flags
├── muslimpro/           (137)  # Main app module, activities, DI
│   ├── application/      (12)  # App initializers
│   ├── base/              (5)  # Base classes
│   ├── core/             (64)  # Core activities, services
│   ├── databinding/      (48)  # ViewBinding generated code
│   └── p058di/            (7)  # App-level DI module
│
├── # --- RELIGIOUS FEATURES ---
├── prayer/               (92)  # Prayer times engine
├── quran/               (558)  # Full Quran reader/player
├── qibla/                 (7)  # Qibla compass
├── dua/                  (33)  # Supplications
├── tasbih/               (34)  # Digital rosary
├── names/                 (7)  # 99 Names of Allah
├── calendar/             (17)  # Islamic calendar
├── fasting/              (11)  # Ramadan tracker
├── zakat/                (32)  # Zakat calculator
├── shahadah/              (4)  # Shahada declaration
│
├── # --- CONTENT & MEDIA ---
├── inspiration/          (87)  # Daily content feed
├── dailydeen/            (25)  # Daily Islamic content
├── story/                (32)  # Stories system
├── deenmode/             (51)  # Focused mode
├── quranlesson/          (16)  # Learning
├── quranmemorization/    (22)  # Memorization
├── quransearch/          (37)  # Search engine
│
├── # --- VIDEO PLATFORM (QALBOX) ---
├── qalboxdata/          (212)  # ★ Video data layer + network module
├── qalboxmobile/        (123)  # Video player UI
├── meccalive/             (6)  # Mecca live stream
├── casting/               (6)  # Chromecast
├── customplayer/         (11)  # Custom player
├── mediaplayer/           (4)  # Media controller
│
├── # --- SOCIAL & COMMUNITY ---
├── community/           (182)  # Social features
├── journal/              (84)  # Personal journal
├── gamification/        (106)  # Achievements/badges
├── profile/              (19)  # User profile
│
├── # --- COMMERCE ---
├── premium/              (62)  # Premium features
├── purchase/             (16)  # IAP logic
├── freetrial/            (20)  # Trial management
├── marketplace/          (15)  # Marketplace
│
├── # --- PLACES & TRAVEL ---
├── places/               (50)  # Places discovery
├── halalplaces/           (3)  # Halal finder
├── hajjjourney/          (24)  # Hajj guide
├── hajjumrah/            (14)  # Hajj/Umrah
├── umrahme/              (17)  # Umrah booking
│
├── # --- INFRASTRUCTURE ---
├── ads/                  (39)  # Ad management
├── analytics/             (3)  # Analytics
├── location/             (35)  # Location services
├── notification/          (2)  # Push notifications
├── notificationcentre/    (7)  # Notification center UI
├── syncmanager/          (13)  # Data sync
├── widget/               (48)  # Home screen widgets
├── commonui/             (58)  # Shared UI components
├── sharedui/             (17)  # Shared UI elements
├── components/           (12)  # Reusable components
├── onboarding/           (24)  # Onboarding flow
├── onboardingui/         (32)  # Onboarding UI
├── today/                (66)  # Today/home screen
├── timeline/             (59)  # Timeline view
├── timelinev2/           (23)  # Timeline v2
├── model/                (70)  # Core data models
└── ... (remaining smaller modules)
```

### Obfuscated Code (`defpackage/`)
**17,135 files — ObfUSCATED by ProGuard/R8**

These contain renamed classes in the default package. Key patterns:
- `AbstractC0xxx` — Abstract base classes
- `C0xxx` — Concrete classes
- `EnumC0xxx` — Enumerations
- `InterfaceC0xxx` — Interfaces
- Many Jetpack Compose runtime classes (large file sizes indicate generated composables)

### Third-Party Libraries
Libraries are included as decompiled source (not as JARs):
- `androidx/` (14,900) — Full AndroidX library source
- `com/google/` (12,458) — Firebase, Play Services, Ads
- `com/facebook/` (2,441) — Facebook SDK
- `com/bytedance/` (1,272) — TikTok/ByteDance SDK

---

## Key Entry Points

| Entry Point | File | Purpose |
|---|---|---|
| App Class | `muslimpro/core/MPApplication` | Application lifecycle |
| Launcher | `muslimpro/core/activities/SplashActivity` | Entry + deep links |
| Network | `qalboxdata/data/p074di/QalboxNetworkModule` | API configuration |
| API Client | `api/p024di/` | Core API DI module |
| Auth | `authentication/` (51 files) | Login/signup flows |
