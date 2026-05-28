---
id: cairn-library
title: Cairn Library
sidebar_position: 2
---

## What is the Cairn Library?

A language-agnostic (aspirational) client library that provides a stable interface for applications to interact with Cairn modules in a native way. The library abstracts away the underlying communication and contract details of modules, providing a consistent and intuitive API for developers that feels clean and precise.

## What it does

- Provides namespaced access to module APIs and events.
- Handles communication, serialization, and contract adherence with modules. There is no need for boilerplate code for request formatting, response parsing, or error handling when interacting with modules.
- Provides a stable interface that decouples application code from internal module implementations, allowing for flexibility and evolution of modules without breaking user applications.
