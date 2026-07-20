# Guideline: State Machine Design

## Purpose

These are the mandatory rules for the operational state machine of an
OpenMower-class robotic mowing system. Any architecture or design document
describing the state machine must satisfy every rule below without
contradiction.

## Transition Integrity Rules

1. Every behavior's execution must return a valid next behavior when it
   completes. A behavior must never return a null or undefined next
   behavior as part of normal operation; a null current behavior is only
   permitted as a critical error condition that itself triggers an
   emergency.
2. If the current behavior is null, the system must treat this as a
   critical error and set emergency mode. The system must not attempt to
   continue normal operation with no active behavior.
3. The mowing behavior must transition only to the docking behavior or
   remain in the mowing behavior. A transition directly from the mowing
   behavior to the idle behavior without passing through docking is not
   permitted.
4. The mowing behavior must transition toward docking whenever any of the
   following occurs: battery level drops low, rain is detected while rain
   mode is enabled, the mower motor temperature exceeds the configured hot
   threshold, the mowing task completes, or an explicit home command is
   issued.
5. The idle (docked) behavior must transition to the undocking behavior
   before it can reach the mowing behavior. A direct transition from idle
   (docked) to mowing without undocking first is not permitted.
6. The docking behavior must transition to the idle (docked) behavior only
   once charging has been detected. A transition to idle (docked) before
   charging is detected is not permitted.

## Emergency Interaction Rules

7. When an emergency is triggered, the safety system must request the
   currently active behavior to pause before any further state transition
   is allowed to proceed. A state transition must not occur while an
   emergency pause request is unacknowledged.
8. If a behavior cannot continue after an emergency is cleared, it must
   abort and transition toward docking or idle rather than resuming an
   unsafe operation.
9. If the current behavior requires GPS and a GPS timeout is active, the
   system must stop the blade and stop movement while keeping the current
   behavior active; it must not silently continue driving without GPS.

## Automatic Start Rules

10. Automatic mode must not start a mowing session unless all of the
    following are true simultaneously: the battery is full, the motor is
    cool, manual pause is not active, and rain delay is not active. If any
    one of these conditions is false, automatic mode must not initiate
    undocking or mowing.
11. Manual mode must only respond to an explicit start command; it must
    never auto-start a mowing session on its own.
12. Semi-automatic mode must complete at most one mowing task before
    returning to idle; it must not continuously restart mowing sessions
    without a new explicit trigger.

## Command Handling Rules

13. The delete-maps command must only be permitted while the system is in
    the idle or area-recording state. Deleting maps while the mower is
    actively mowing, docking, or undocking is not permitted.
14. The reset-emergency command must only clear the latched emergency
    state; it must not, by itself, command the mower to start moving or
    start mowing.
