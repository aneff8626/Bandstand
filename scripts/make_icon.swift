import AppKit
let out=CommandLine.arguments[1]
let image=NSImage(size:NSSize(width:1024,height:1024))
image.lockFocus()
NSColor.clear.setFill();NSRect(x:0,y:0,width:1024,height:1024).fill()
let tile=NSBezierPath(roundedRect:NSRect(x:64,y:64,width:896,height:896),xRadius:200,yRadius:200)
NSGradient(starting:NSColor(srgbRed:0.055,green:0.32,blue:0.29,alpha:1),ending:NSColor(srgbRed:0.13,green:0.56,blue:0.46,alpha:1))!.draw(in:tile,angle:70)
let wave=NSBezierPath();wave.move(to:NSPoint(x:195,y:435));wave.line(to:NSPoint(x:285,y:435));wave.curve(to:NSPoint(x:382,y:680),controlPoint1:NSPoint(x:325,y:435),controlPoint2:NSPoint(x:312,y:680));wave.curve(to:NSPoint(x:494,y:370),controlPoint1:NSPoint(x:461,y:680),controlPoint2:NSPoint(x:443,y:370));wave.curve(to:NSPoint(x:611,y:640),controlPoint1:NSPoint(x:548,y:370),controlPoint2:NSPoint(x:542,y:640));wave.curve(to:NSPoint(x:735,y:435),controlPoint1:NSPoint(x:684,y:640),controlPoint2:NSPoint(x:674,y:435));wave.line(to:NSPoint(x:828,y:435));wave.lineWidth=49;wave.lineCapStyle = .round;wave.lineJoinStyle = .round;NSColor(srgbRed:0.97,green:0.98,blue:0.9,alpha:1).setStroke();wave.stroke()
NSColor(srgbRed:0.93,green:0.73,blue:0.38,alpha:1).setFill();NSBezierPath(ovalIn:NSRect(x:782,y:684,width:56,height:56)).fill()
image.unlockFocus()
let rep=NSBitmapImageRep(data:image.tiffRepresentation!)!;try rep.representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:out))
