# Muslim Pro — Decompiled APK Documentation Index

> **Project:** Muslim Pro v17.0.4
> **Package:** `com.bitsmedia.android.muslimpro`
> **Scan Date:** 2026-02-28
> **Scan Mode:** Exhaustive

---

## 📋 Documentation Files

| # | Document | Description | Status |
|---|---|---|---|
| 1 | [Project Overview](project-overview.md) | Executive summary, tech stack, feature list, deep links | ✅ Complete |
| 2 | [Architecture](architecture.md) | High-level architecture, DI graph, networking, UI system, SDKs, security | ✅ Complete |
| 3 | [Source Tree Analysis](source-tree-analysis.md) | Annotated directory tree with file counts, critical paths, entry points | ✅ Complete |
| 4 | [Component Inventory](component-inventory.md) | Complete inventory of 104 feature modules, UI & infrastructure components | ✅ Complete |
| 5 | [API Contracts](api-contracts.md) | Network stack, API domains, REST patterns, deep link URI scheme | ✅ Complete |
| 6 | [Data Models](data-models.md) | Model architecture, serialization, 350+ model files documented | ✅ Complete |
| 7 | [Development Guide](development-guide.md) | RE tools, browsing strategies, analysis techniques, key files | ✅ Complete |
| 8 | [Scan Report](project-scan-report.json) | Workflow state & scan metadata | ✅ Complete |

---

## 🔑 Quick Reference

### Key Numbers
- **58,781** total decompiled files
- **3,183** app source files (under `com.bitsmedia.android`)
- **104** feature modules
- **30+** deep link URI handlers
- **73+** supported locales
- **9** DEX files (~102MB)
- **6** supported ABIs (arm64-v8a, armeabi-v7a, x86, x86_64)

### Key Entry Points
| Purpose | Location |
|---|---|
| Application class | `com.bitsmedia.android.muslimpro.core.MPApplication` |
| Launcher activity | `com.bitsmedia.android.muslimpro.core.activities.SplashActivity` |
| Network module | `com.bitsmedia.android.qalboxdata.data.p074di.QalboxNetworkModule` |
| API layer | `com.bitsmedia.android.api.*` |
| Auth module | `com.bitsmedia.android.authentication.*` |

### Quick Start for Analysis
1. **Start with** → [Project Overview](project-overview.md) for context
2. **Understand structure** → [Source Tree Analysis](source-tree-analysis.md)
3. **Find specific features** → [Component Inventory](component-inventory.md)
4. **Analyze APIs** → [API Contracts](api-contracts.md)
5. **Deep dive code** → [Development Guide](development-guide.md)

---

## ⚠️ Important Notes

- This is a **decompiled APK** — code has been through ProGuard/R8 obfuscation
- Classes in `defpackage/` (17,135 files) are obfuscated — focus on `com.bitsmedia.android.*`
- Build files are auto-generated skeletons — project **cannot be compiled**
- Some class/method names are **not original** — use `@Metadata` annotations for Kotlin source info
- Library source code (55K+ files) is included in decompilation — ignore for app analysis
