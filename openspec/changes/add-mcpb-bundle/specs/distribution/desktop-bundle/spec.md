## Purpose

The Claude Desktop distribution channel: an installable bundle that lets a desktop user run this
server without a terminal, a Python toolchain, or a hand-edited configuration file, while
guaranteeing that what they install is exactly a published release.

## ADDED Requirements

### Requirement: Every release carries an installable bundle

Each GitHub release SHALL carry a bundle asset, downloadable from a stable URL that always resolves
to the newest release. A release that publishes the package to PyPI without attaching the bundle is
incomplete.

#### Scenario: The published button never 404s

- **WHEN** a visitor follows the bundle download link in the README
- **THEN** the newest release serves a bundle asset, and the download does not 404

#### Scenario: Bundle version tracks the release tag

- **WHEN** a bundle attached to release `vX.Y.Z` is inspected
- **THEN** the version it declares is `X.Y.Z`, matching the tag and the package published to PyPI

### Requirement: The bundle cannot drift from a published release

The bundle SHALL NOT contain server source code. It SHALL install the server by resolving an exact
pinned version of the published package, so the code a bundle user runs is byte-identical to the
code PyPI serves for that version.

#### Scenario: Bundle contents carry no server modules

- **WHEN** a packed bundle is unpacked and its contents listed
- **THEN** no module of this project's server implementation is present, only a manifest, a
  dependency declaration, and a launcher that imports the installed package

#### Scenario: The pin is exact, not a range

- **WHEN** the bundle's dependency declaration is read
- **THEN** it names one exact version, so a later PyPI release cannot silently change what an
  already-downloaded bundle installs

### Requirement: The user supplies the API key through the host

The bundle SHALL collect the London Strategic Edge API key through the host application's own
configuration interface, marked sensitive so the host conceals it, and pass it to the server as the
`LSE_API_KEY` environment variable.

#### Scenario: Install prompts for the key

- **WHEN** a user installs the bundle
- **THEN** the host prompts for an API key before the server is first started

#### Scenario: A missing key is refused at install, not at first call

- **WHEN** a user attempts to complete installation with the key field left blank
- **THEN** the host refuses to complete installation, rather than installing a server that fails on
  its first tool call

#### Scenario: The key is never persisted by the project

- **WHEN** a bundle is installed and used
- **THEN** the key exists only in the host's own storage and the server process environment; the
  project writes it to no file, log, or repository artifact

### Requirement: A bundle install does not depend on the OS credential store

A server started from the bundle SHALL serve tool calls on a host where the operating system
credential store is unavailable or refuses access to a sandboxed process.

#### Scenario: Sandboxed host with no credential-store access

- **GIVEN** a host on which the OS credential store denies access to the server process
- **WHEN** the user installs the bundle, supplies a valid key, and issues a tool call
- **THEN** the call returns rows, and no credential-store error is surfaced

### Requirement: The documented install path states its prerequisites

If installing from the bundle requires anything the host does not itself supply, the README SHALL
state that prerequisite adjacent to the install button. If the prerequisite cannot be stated
honestly as a one-step action, the button SHALL NOT be published and the bundle SHALL be offered as
a manual download instead.

#### Scenario: The host supplies everything needed

- **WHEN** the host is verified to provide the bundle's runtime without user setup
- **THEN** the README publishes the install button with no prerequisite text

#### Scenario: The host does not supply the runtime

- **WHEN** installation is verified to fail on a machine lacking the runtime
- **THEN** the README either states that prerequisite next to the button, or omits the button and
  documents the manual download
