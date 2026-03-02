# Muslim Pro — Data Models

> **Source:** Decompiled APK analysis
> **Total model files:** ~350+ across feature modules

---

## Model Layer Overview

The app uses a multi-layered data model approach:

```
Remote DTOs (API response objects)
    ↓ Mappers
Domain Models (business objects)
    ↓ Mappers
Local Entities (Room database)
    ↓ ViewModels
UI State (Compose state / LiveData)
```

---

## Core Models (`com.bitsmedia.android.model/` — 70 files)

Root-level business models shared across features. These represent the core domain objects of the application, including prayer data, user profiles, settings, and cross-cutting concerns.

---

## Qalbox Video Models (`qalboxdata/model/` — 203 files)

The largest model package, supporting the Qalbox video platform:

### Expected Model Categories
- **Content Models**: Video metadata, thumbnails, duration, categories
- **User Models**: Watch history, favorites, playlist membership
- **Streaming Models**: Playback URLs, quality options, DRM tokens
- **Catalog Models**: Genre, category, collection, featured content
- **Analytics Models**: Watch progress, engagement metrics

---

## Feature-Specific Models

### Prayer Models
Located in `prayer/` (92 files total):
- Prayer time calculations
- Calculation method parameters
- Location-prayer mapping
- Notification scheduling data

### Quran Models
Located in `quran/` (558 files total):
- Surah/Ayah data structures
- Audio recitation metadata
- Translation content
- Bookmarks, highlights, notes
- Khatam progress tracking
- Memorization progress

### Iqra/Learning Models (`iqra_data/` — 63 files)
Course and lesson data for Quran learning:
- Course structure
- Lesson progress
- Assessment data
- Certificate tracking

### Content/Inspiration Models
Located in `inspiration/data/`:

**`remote/ImagesDto`** (Parcelable):
```java
class ImagesDto {
    String storyUrl;   // URL to story content
    String baseUrl;    // Base URL for image assets
}
```

**`model/Images`** (Serializable):
```java
class Images {
    String storyUrl;   // Story URL
    String baseUrl;    // Base image URL
}
```

### Story Models
Located in `story/data/remote/`:

**`ImagesDto`** (Parcelable):
```java
class ImagesDto {
    String storyUrl;   // Story/article URL
    String baseUrl;    // Image base URL
}
```

### Community Models (`community/` — 182 files)
- User posts and comments
- Reactions and interactions
- User profiles in community context
- Moderation data

### Gamification Models (`gamification/` — 106 files)
- Achievement definitions
- Badge metadata
- Streak data
- Progress milestones
- Reward configurations

### Journal Models (`journal/` — 84 files)
- Journal entries
- Entry metadata (date, mood, tags)
- Attachment data

### Premium/Commerce Models
- Subscription tiers
- Purchase records
- Trial status
- Product catalog

---

## Serialization Strategies

### Moshi (Square)
```java
// Custom adapters in api/adapter/ (7 files)
// JSON field mapping with @Json annotations
```

### Kotlinx Serialization
```java
// @Serializable annotations in Kotlin data classes
// Custom serializers for complex types
// Preserved in @Metadata annotations
```

### Android Parcelable
```java
// Many DTOs implement Parcelable for IPC
// writeToParcel / createFromParcel patterns
// Used for deep link data passing
```

### Room Entities
```java
// @Entity annotations for database tables
// @Dao interfaces for queries
// TypeConverters for complex fields
```

---

## Localization Data

The app supports **73+ locales** with localized string resources:

```
res/values/          — Default (English)
res/values-ar/       — Arabic
res/values-az/       — Azerbaijani
res/values-bn/       — Bengali
res/values-da/       — Danish
res/values-de/       — German
res/values-es/       — Spanish
res/values-ff/       — Fula
res/values-fr/       — French
res/values-hi/       — Hindi
res/values-in/       — Indonesian
res/values-it/       — Italian
res/values-ja/       — Japanese
res/values-ms/       — Malay
res/values-nl/       — Dutch
res/values-pt/       — Portuguese
res/values-ru/       — Russian
res/values-th/       — Thai
res/values-tr/       — Turkish
res/values-ug/       — Uyghur
res/values-ur/       — Urdu
res/values-zh/       — Chinese
res/values-zh-rCN/   — Chinese (Simplified)
... and 50+ more
```
