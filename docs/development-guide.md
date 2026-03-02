# Muslim Pro — Development Guide (Reverse Engineering)

> **Context:** This is a decompiled APK, not an original source project
> **Purpose:** Reverse engineering, API analysis, and code understanding

---

## Prerequisites

### Required Tools
- **JADX** or **JADX-GUI** — For interactive decompilation and browsing
- **apktool** — For resource extraction and manifest decoding
- **dex2jar** — For DEX to JAR conversion
- **JD-GUI** — Alternative Java decompiler
- **Android Studio** — For code browsing (import as project)
- **Charles Proxy / mitmproxy** — For API traffic interception
- **Frida** — For dynamic instrumentation

### Environment Setup
- Java 8+ (for decompiler tools)
- Android SDK (for manifest and resource understanding)
- Python 3.x (for scripting analysis)

---

## Project Structure

The decompiled project follows Android Gradle structure:
```
decoded/
├── build.gradle          # Root build file (AGP 8.10.1)
├── settings.gradle       # rootProject.name = 'UNKNOWN'
└── app/
    ├── build.gradle      # App module (placeholder deps)
    └── src/main/
        ├── java/         # Decompiled source
        └── res/          # Extracted resources
```

> **Note:** The `build.gradle` files are auto-generated skeletons from the decompiler.
> They cannot be used to build the project — dependencies are listed as `TODO`.

---

## Browsing the Code

### Opening in Android Studio
1. Open the `decoded/` folder as an existing Android project
2. Android Studio will index the files (may take 10-20 minutes due to ~58K files)
3. Ignore build errors — this project is for reading, not building
4. Use **Find in Files** (Ctrl+Shift+F) to search across the codebase

### Key Browse Paths

#### Start with the App Core
```
com.bitsmedia.android.muslimpro.core.MPApplication  → Application class
com.bitsmedia.android.muslimpro.core.activities.SplashActivity → Entry point
```

#### API & Networking
```
com.bitsmedia.android.qalboxdata.data.p074di.QalboxNetworkModule → Main network config
com.bitsmedia.android.api.*  → Core API layer
```

#### Feature Modules
Each feature follows a similar structure:
```
com.bitsmedia.android.{feature}/
├── data/           # Repository, DTOs, data sources
│   ├── remote/     # API DTOs
│   ├── local/      # Room DAOs, entities
│   └── repository/ # Repository implementations
├── domain/         # Use cases, domain models
├── presentation/   # Activities, Fragments, ViewModels
└── di/             # Dagger/Hilt module (often named p0XXdi/)
```

---

## Analysis Techniques

### Finding API Endpoints
1. Search for URL strings: `grep -r "https://" --include="*.java"`
2. Look for Retrofit interfaces: search for classes with `@GET`, `@POST` patterns
3. Check `QalboxNetworkModule` for base URL configuration
4. Look for `OkHttpClient` builder patterns for interceptors

### Finding API Keys & Secrets
```bash
# Search for hardcoded secrets
grep -rn "api_key\|apiKey\|API_KEY\|secret\|SECRET\|token\|TOKEN" --include="*.java"
grep -rn "https://\|http://" --include="*.java" | grep -v "schemas.android"
```

### Understanding Obfuscated Code
- Classes in `defpackage/` are R8/ProGuard obfuscated
- Look at `@Metadata` annotations for Kotlin class info
- Cross-reference with `R.java` for resource ID mapping
- Method signatures often reveal original names in metadata

### Analyzing Data Models
```bash
# Find all Parcelable data classes
grep -rn "implements Parcelable" --include="*.java"
# Find Moshi JSON adapters  
grep -rn "JsonAdapter" --include="*.java"
# Find serializable models
grep -rn "@Serializable\|@SerializedName\|@Json" --include="*.java"
```

### Tracing Deep Link Handlers
1. Open `AndroidManifest.xml` (3,792 lines)
2. Search for `<intent-filter>` with `muslimpro://` scheme
3. Each `android:host` value maps to a feature handler
4. Trace the handler in `SplashActivity` to find routing logic

---

## Key Files for Reverse Engineering

| Priority | File | Why |
|---|---|---|
| ★★★ | `AndroidManifest.xml` | All activities, permissions, deep links, API keys |
| ★★★ | `QalboxNetworkModule.java` | Network configuration, base URLs, interceptors |
| ★★★ | `MPApplication.java` | App initialization, SDK setup |
| ★★ | `api/p024di/` | Core API DI module |
| ★★ | `R.java` | Resource ID mapping (1.38 MB) |
| ★★ | `config/` | Feature flags, remote config |
| ★★ | `authentication/` | Auth flow, token management |
| ★ | `*.properties` files | Library versions |
| ★ | `META-INF/` | Signing certificates |

---

## Common Challenges

### 1. Obfuscated Names
Many classes have names like `C0065xef2dafc5`. Use:
- KDoc/Metadata annotations
- String constants within the class
- Method signatures and parameters
- Usage context from callers

### 2. Decompiler Artifacts
- `goto` statements (from optimized bytecode)
- Inline function expansion (Kotlin)
- Synthetic lambda classes (`ExternalSyntheticLambda0`)
- Missing generics information

### 3. Very Large Files
Some decompiled files are 100KB+:
- Generated composables
- Databinding mappers
- Heavily-inlined Kotlin code

### 4. Library Code Noise
~55K of ~58K files are library code. Focus on `com.bitsmedia.android.*` (3,183 files).
