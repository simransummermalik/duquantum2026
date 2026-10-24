# Watchcat Expression States

Watchcat is the pixel-art detective cat that lives alongside the quantum
simulation. Its expressions make the numerical results easy to notice, while
the actual scientific decision always comes from Watchcat's measured
diagnostics.

## Idle — current look

<p align="center">
  <img src="assets/watchcat-idle.gif" alt="Watchcat animated idle detective look" width="320" />
</p>

The idle look is Watchcat calmly investigating with its magnifying glass. The
full idle animation is the supplied
[`ui/watchcat_idle.html`](ui/watchcat_idle.html): it runs the original canvas animation directly, including blinking, eye movement, tail movement, gentle bobbing, and magnifying-glass movement.

## Expression states

| State | Animation | When it appears |
| --- | --- | --- |
| **Idle** | [`watchcat_idle.html`](ui/watchcat_idle.html) | No simulation is running |
| **Watching** | [`watchcat_watching.html`](ui/watchcat_watching.html) | A simulation or convergence check is running |
| **Worried** | [`watchcat_worried.html`](ui/watchcat_worried.html) | A truncation, trace, or accuracy check looks unreliable |
| **Happy** | [`watchcat_happy.html`](ui/watchcat_happy.html) | The result passes the requested checks |
| **Celebrating** | [`watchcat_super_excited.html`](ui/watchcat_super_excited.html) | A cheaper validated configuration is found |
| **Sleeping** | [`watchcat_bedtime.html`](ui/watchcat_bedtime.html) | Watchcat is inactive for a while |

## Important design rule

An expression is a communication layer, not a scientific measurement. Watchcat
will always show the numerical evidence next to the animation, including the
tested truncation, observable differences, tolerance, runtime, and validation
result.

## Implementation status

- **Idle animation:** available at [`ui/watchcat_idle.html`](ui/watchcat_idle.html).
- **Watching animation:** available at [`ui/watchcat_watching.html`](ui/watchcat_watching.html).
- **Worried animation:** available at [`ui/watchcat_worried.html`](ui/watchcat_worried.html).
- **Happy animation:** available at [`ui/watchcat_happy.html`](ui/watchcat_happy.html).
- **Celebrating animation:** available at [`ui/watchcat_super_excited.html`](ui/watchcat_super_excited.html).
- **Sleeping animation:** available at [`ui/watchcat_bedtime.html`](ui/watchcat_bedtime.html).
- **Markdown preview:** an animated fallback GIF is available at [`assets/watchcat-idle.gif`](assets/watchcat-idle.gif).
- **Static README artwork:** available at [`assets/watchcat.svg`](assets/watchcat.svg).
