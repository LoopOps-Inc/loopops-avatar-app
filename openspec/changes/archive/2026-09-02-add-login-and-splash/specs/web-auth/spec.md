# Web Auth Specification

## Purpose

`/` shows a branded splash then ClientId/password login. Success stores the token and opens `/demo`. Unauthenticated `/demo` returns to `/`. Session start does not pick an investor or mint.

## Requirements

### Requirement: Splash overlay on entry

The app MUST show a timed navy-and-gold splash overlay on `/` when motion is allowed. The overlay MUST NOT appear when reduced motion is preferred or a valid token exists. Login MUST remain on `/` with no splash-only or login-only path.

#### Scenario: Splash then login

- GIVEN unauthenticated visitor, motion allowed
- WHEN they open `/`
- THEN a timed splash overlay shows, then the login form

#### Scenario: Reduced motion skips overlay

- GIVEN unauthenticated visitor who prefers reduced motion
- WHEN they open `/`
- THEN login shows immediately with no overlay

#### Scenario: Valid token skips overlay

- GIVEN a valid stored token
- WHEN they open `/`
- THEN the overlay is omitted and they are not left on login

### Requirement: Login credentials and mint request

Login on `/` MUST collect a numeric ClientId and password. The mint request MUST include `password` and `client_id` as the entered digit string. Aliases like `cl_demo_moderado` MUST NOT be accepted. Empty ClientId or password MUST NOT send a mint request.

#### Scenario: Digit ClientId submits

- GIVEN the login form
- WHEN they enter `200001` and a password and submit
- THEN a mint request is sent with `client_id` `"200001"` and `password`

#### Scenario: Alias ClientId rejected

- GIVEN the login form
- WHEN they enter `cl_demo_moderado` and submit
- THEN no mint request uses that alias as `client_id`, and they stay on login with feedback

#### Scenario: Empty credentials

- GIVEN the login form
- WHEN ClientId or password is empty and they submit
- THEN no mint request is sent and they stay on login

### Requirement: Successful authentication

A successful mint MUST store the issued token and MUST open `/demo`. The password MUST NOT be stored.

#### Scenario: Valid credentials land on demo

- GIVEN valid ClientId and password
- WHEN mint succeeds
- THEN the token is stored, they are on `/demo`, and the password is not persisted

#### Scenario: Failed mint stays on login

- GIVEN rejected credentials
- WHEN mint fails
- THEN no new token is stored and they stay on login

### Requirement: Route guards

Unauthenticated `/demo` MUST redirect to `/`. Authenticated `/` MUST redirect to `/demo`. Missing or invalid tokens MUST count as unauthenticated.

#### Scenario: Unauthenticated demo redirects home

- GIVEN a missing or invalid token
- WHEN they open `/demo`
- THEN they redirect to `/` and see login after splash rules

#### Scenario: Authenticated home redirects to demo

- GIVEN a valid stored token
- WHEN they open `/`
- THEN they redirect to `/demo`

### Requirement: Session start has no identity mint

The session start surface MUST NOT show an investor picker and MUST NOT mint a token. Login MUST be the only identity switcher.

#### Scenario: Start session without picker

- GIVEN authenticated visitor on `/demo`
- WHEN they use session start
- THEN no investor picker is shown and no mint request is sent from that surface

#### Scenario: Repeat start does not mint

- GIVEN authenticated visitor on `/demo`
- WHEN they start a session again
- THEN no mint request is sent from that surface

### Requirement: Auth errors and password privacy

`UNAUTHENTICATED` and `VALIDATION_ERROR` MUST map to user-facing copy. The password MUST NOT persist.

#### Scenario: Unauthenticated maps to copy

- GIVEN mint outcome `UNAUTHENTICATED`
- WHEN login finishes with that error
- THEN mapped user-facing copy is shown and the password is not persisted

#### Scenario: Validation error maps to copy

- GIVEN mint outcome `VALIDATION_ERROR`
- WHEN login finishes with that error
- THEN mapped user-facing copy is shown and they stay on login
