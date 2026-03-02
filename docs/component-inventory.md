# Muslim Pro — Component Inventory

> **Source:** Decompiled APK analysis
> **Total Feature Modules:** 104
> **Total App Source Files:** ~3,183

---

## UI Components

### Common UI (`commonui/` — 58 files)
Shared UI component library used across features. Contains:
- Custom views, dialogs, bottom sheets
- Reusable list items, cards
- Common animations and transitions

### Shared UI (`sharedui/` — 17 files)
Additional shared UI elements:
- Header/toolbar components
- Loading states, empty states
- Error handling views

### Compose UI System
- `composeui/` (1 file) — Compose integration bridge
- `designsystem/` (1 file) — Design tokens/theme
- `components/` (12 files) — Reusable Compose components

### Data Binding (`databinding/` — 48 files)
Generated ViewBinding classes for XML layouts.

---

## Feature Components by Category

### Prayer System (92 files)
- Prayer time calculation engine
- Multiple calculation methods
- Notification/alarm scheduling
- Widget components for home screen
- Monthly prayer timetable
- Prayer tracker/logger

### Quran Reader (558 files)
- Full Quran text rendering (Arabic + translations)
- Audio recitation player
- Search engine (37 files in `quransearch/`)
- Bookmarking system
- Khatam (reading completion) tracking
- Memorization tools (22 files)
- Lesson system (16 files)
- Theme customization

### Qalbox Video Platform (335 files total)
- **Data layer** (`qalboxdata/` — 212 files): Video content models, network module, repository
- **Mobile UI** (`qalboxmobile/` — 123 files): Player, browsing, categories

### Community System (182 files)
- Social feed
- User interactions
- Content sharing
- Community features

### Gamification Engine (106 files)
- Achievement system
- Streak tracking
- Badge awards
- Progress milestones

### Inspiration/Content (144 files)
- `inspiration/` (87 files) — Content feed, articles
- `dailydeen/` (25 files) — Daily content
- `story/` (32 files) — Story format content

### Journal (84 files)
- Personal diary/journal
- Entry creation and management
- Mood/reflection tracking

### Premium & Commerce (113 files)
- `premium/` (62 files) — Premium feature gates
- `purchase/` (16 files) — IAP logic
- `freetrial/` (20 files) — Trial management
- `marketplace/` (15 files) — Digital marketplace

### Places & Travel (111 files)
- `places/` (50 files) — Places browsing
- `halalplaces/` (3 files) + `halalplacesdetail/` (5 files) — Halal finder
- `hajjjourney/` (24 files) — Hajj guide
- `hajjumrah/` (14 files) — Hajj/Umrah
- `umrahme/` (17 files) — Umrah booking

### Authentication (51 files)
- Login/signup flows
- Social login (Facebook, Google)
- Firebase Auth integration
- Session management

### Advertising (39 files)
- Ad loading/display management
- Multiple ad network mediation
- Ad placement configuration

### Home Screen Widgets (48 files)
- Prayer time widgets
- Quick access widgets
- Customizable widget themes

### Onboarding (56 files)
- `onboarding/` (24 files) — Onboarding logic
- `onboardingui/` (32 files) — Onboarding screens

---

## Data Model Components

### Core Models (`model/` — 70 files)
Root-level business objects used across features.

### Qalbox Models (`qalboxdata/model/` — 203 files)
Extensive video platform data models including:
- Video content DTOs
- Category/genre models
- Playback state models
- Streaming configuration
- Content metadata

### API Models
- `api/model/` (5 files) — Core API objects
- `api/response/` (4 files) — Response wrappers
- `api/adapter/` (7 files) — Type adapters

### Feature-Specific DTOs
- `inspiration/data/remote/` — Content DTOs (ImagesDto, etc.)
- `story/data/remote/` — Story DTOs
- `iqra_data/` (63 files) — Iqra course data models

---

## Infrastructure Components

| Component | Package | Files | Purpose |
|---|---|---|---|
| Base Framework | `base/` | 153 | Base activities, fragments, utilities |
| Core | `core/` | 40 | Application core, main activities |
| Config | `config/` | 19 | Remote config, feature flags |
| Analytics | `analytics/` | 3 | Analytics abstraction |
| Location | `location/` | 35 | GPS, location services |
| Sync | `syncmanager/` | 13 | Data synchronization engine |
| Notifications | `notification/` + `notificationcentre/` | 9 | Push notification handling |
| File Handler | `filehandler/` | 1 | File I/O operations |
| FlowBus | `flowbus/` | 1 | Event bus (Kotlin Flow) |
| Consent | `consent/` | 5 | GDPR/privacy consent |
| Permissions | `permission/` | 1 | Runtime permissions |
| NPS | `nps/` | 16 | User satisfaction surveys |
| Feedback | `feedback/` | 2 | User feedback collection |
| In-App Update | `inappupdate/` | 3 | App update prompts |
