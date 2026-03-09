---
id: overview-system-design
title: Overview & System Design
sidebar_position: 1
---

This section explains how the Cairn SDK is structured at a high level and how its components relate to and work with one another.

## Conceptual layers

- **User/Application layer**: Your product/app logic.
- **SDK library layer**: SDK client library and APIs.
- **Module layer**: SDK Modules providing core capabilities like camera management, inference, and messaging.
- **Device layer**: The device and its resources.


Below is a high-level view of how Cairn SDK components fit together for an application flow.

```mermaid
%%{init: {'theme':'base','themeVariables':{
  'background':'#0b162a',
  'primaryColor':'#123c70',
  'primaryTextColor':'#eaf3ff',
  'primaryBorderColor':'#72c9ef',
  'edgeLabelBackground':'#245282',
  'lineColor':'#72c9ef',
  'tertiaryColor':'#0f233f',
  'fontFamily':'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial'
}}}%%
graph LR;
    APP[User App] --> SDK[Cairn Client Library];

    subgraph MODULES[Cairn Modules]
      direction TB
      ENTRY(( ))
      CAM[Camera Module]
      INF[Inference Module]
      BUS[Messaging Module]

      ENTRY --> CAM
      ENTRY --> INF
      ENTRY --> BUS
    end

    SDK --> ENTRY;
    CAM --> HW[Camera Hardware];
    INF --> CPU[Device];
    BUS -->|  event notifications  | APP;

    classDef app fill:#0f315d,stroke:#7edaf6,color:#eaf6ff,stroke-width:2px;
    classDef core fill:#11507a,stroke:#86dffb,color:#eaf6ff,stroke-width:2px;
    classDef infra fill:#1a355a,stroke:#6dc3e6,color:#deeeff,stroke-width:2px;
    classDef modules fill:#245282,stroke:#b8efff,color:#f3faff,stroke-width:3px;
    classDef hidden fill:transparent,stroke:transparent,color:transparent;

    class APP app;
    class SDK,CAM,INF,BUS core;
    class HW,CPU infra;
    class MODULES modules;
    class ENTRY hidden;
```
