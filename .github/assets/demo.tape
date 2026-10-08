# Re-record: vhs .github/assets/demo.tape  (run from the repo root; needs vhs, ttyd, ffmpeg)
Output site/demo.gif

Require toolsmoke
Set Shell "bash"
Set FontSize 15
Set FontFamily "JetBrains Mono"
Set Width 1180
Set Height 900
Set Padding 22
Set Margin 0
Set WindowBar Colorful
Set BorderRadius 8
Set Theme {"name": "toolsmoke", "black": "#0d1210", "red": "#f87171", "green": "#4ade80", "yellow": "#fbbf24", "blue": "#60a5fa", "magenta": "#c084fc", "cyan": "#5eead4", "white": "#e7efe9", "brightBlack": "#5c6f66", "brightRed": "#fca5a5", "brightGreen": "#86efac", "brightYellow": "#fde68a", "brightBlue": "#93c5fd", "brightMagenta": "#d8b4fe", "brightCyan": "#99f6e4", "brightWhite": "#ffffff", "background": "#07090a", "foreground": "#e7efe9", "selection": "#1d2a24", "cursor": "#4ade80"}
Set TypingSpeed 45ms
Set Framerate 24
Set PlaybackSpeed 1.0

Hide
Type "source .github/assets/demo-rc.sh && clear"
Enter
Show

Type "toolsmoke --demo broken"
Sleep 300ms
Enter
Sleep 7.5s
Sleep 3.5s

Hide
Type "clear"
Enter
Show

Type "toolsmoke --demo good --only 'tools.*' --only 'stream.*' --only 'json.*'"
Sleep 300ms
Enter
Sleep 4s
Sleep 3.5s
