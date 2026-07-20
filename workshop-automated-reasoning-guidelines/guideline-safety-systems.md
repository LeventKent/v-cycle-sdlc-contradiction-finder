# Guideline: Safety Systems

## Purpose

These are the mandatory safety rules for an OpenMower-class robotic mowing
system. Any architecture, requirements, or design document describing the
safety system must satisfy every rule below without contradiction. Safety
rules take precedence over convenience, performance, or feature requirements.

## Timing Rules

1. The software safety loop that evaluates emergency and safety conditions
   must run at a frequency of at least 2 Hz (i.e. its check interval must be
   500 milliseconds or less).
2. The heartbeat sent from the ROS layer to the firmware layer must be sent
   at an interval of 500 milliseconds or less. A heartbeat interval greater
   than 500 milliseconds is not permitted.
3. If the fused robot pose has not been updated for more than 1.0 second,
   the system must stop the blade and stop all movement. A pose staleness
   threshold greater than 1.0 second before halting movement is not
   permitted.
4. If firmware status messages have not been received for more than 3.0
   seconds, the system must enter full emergency mode. A status staleness
   threshold greater than 3.0 seconds before entering emergency mode is not
   permitted.
5. If the firmware does not receive a heartbeat from the ROS layer within
   its configured timeout, the firmware must autonomously disable the
   motors without waiting for further instruction from the ROS layer.

## Emergency State Rules

6. Emergency state must be latching: once an emergency is triggered, it must
   remain active until an explicit reset command is issued, except for the
   single defined exception below.
7. The only permitted automatic clearing of a latched emergency is when the
   mower is docked and charging and the current behavior is idle or area
   recording. In every other situation, a latched emergency must require an
   explicit reset command to clear.
8. When any emergency condition is active, the blade must be disabled and
   all movement must be stopped. The system must never allow blade
   activation while an emergency is latched (except is not permitted at
   all — blade must always be disabled during emergency).
9. An emergency condition must pause the currently active behavior before
   any state transition occurs. A behavior must not be allowed to continue
   normal execution while an emergency is active.

## Redundancy and Single-Point-of-Failure Rules

10. Hardware-level emergency stop mechanisms (lift/tilt sensors, the
    physical stop button, collision sensors, and the input timeout) must
    function independently of the ROS software layer. A hardware emergency
    stop must not depend on ROS software being reachable or responsive.
11. Any new subsystem or feature added to the mower (including
    connectivity features such as WiFi) must not become a single point of
    failure for the safety system. Loss or failure of a new subsystem must
    not prevent the existing emergency stop chain from functioning.
12. Any new subsystem added to the mower must not block or delay execution
    of the safety loop. A safety loop that can be blocked by a non-safety
    subsystem is not permitted.

## Docking-for-Safety Rules

13. A critically low battery voltage must trigger the mower to return to
    dock. This condition must not be classified as an emergency, because an
    emergency stop would leave the mower stranded rather than able to
    return home.
14. Motor overheating above the configured hot-temperature threshold must
    trigger the mower to return to dock rather than an immediate hard
    emergency stop.
