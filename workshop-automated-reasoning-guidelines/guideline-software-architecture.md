# Guideline: ROS Software Architecture

## Purpose

These are the mandatory architectural rules for the ROS software layer of an
OpenMower-class robotic mowing system. Every ROS package, node, and topic in
the software layer must comply with these rules. This guideline is the source
of truth for reviewing architecture documentation and design proposals.

## Layering Rules

1. The ROS software layer must communicate with hardware only through the
   firmware layer. A ROS package must never access motors, sensors, or other
   physical hardware directly; it must go through a firmware service via the
   communication bridge package.
2. Every ROS package that needs firmware data or must send firmware commands
   must integrate through `mower_comms_v2` (or `mower_comms_v1` for legacy
   serial hardware). A ROS package must not open its own independent channel
   to the firmware mainboard.
3. The state machine package `mower_logic` is the single authority for
   deciding operational behavior (mowing, docking, idle, emergency). No other
   ROS package may command motor movement or blade activation directly; all
   movement and blade commands must flow through `mower_logic` or through
   topics that `mower_logic` arbitrates (e.g. `twist_mux`).
4. The navigation stack must keep path planning and path execution as
   separate concerns. The path planning component must not directly drive
   actuators; it must publish a plan or velocity command that a separate
   execution/control component consumes.
5. A new ROS package must not modify or subclass the internals of
   `mower_logic`'s behavior classes to implement its own logic. New
   functionality must be implemented as a new package that talks to
   `mower_logic` over topics or services, following the same integration
   pattern as existing packages.

## Naming and Interface Rules

6. Topics that carry low-level firmware data must be namespaced under `/ll/`.
   A ROS package must not publish raw firmware register data outside the
   `/ll/` namespace.
7. Topics published by the state machine must be namespaced under
   `/mower_logic/`. A package other than `mower_logic` must not publish to
   the `/mower_logic/` namespace.
8. Any package that introduces a new external communication channel (e.g.
   WiFi, Bluetooth, cellular) must not bypass the existing `/xbot/action`
   action-dispatch mechanism for issuing high-level commands; it must reuse
   that mechanism rather than creating a parallel command path.

## Configuration Rules

9. Parameters must be loaded in the fixed override order: global defaults
   first, then hardware-specific overrides, then user overrides. A package
   must not read configuration from a source outside this parameter
   hierarchy.

## Build and Deployment Rules

10. Every ROS package added to the workspace must be buildable by the
    existing catkin build system. A package must not require a build tool
    other than catkin for the core workspace build.
11. Every new node that is part of normal robot operation must be launched
    from the `open_mower.launch` tree (directly or via an included launch
    file). A node required for normal operation must not be started outside
    the managed launch tree.
