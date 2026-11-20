// Prints a design page's data as JSON: runs the page's own `renderVals()` in Apple's JavaScriptCore, so the website
// shows exactly the text and lists the design has. Functions (tab handlers) are left out; the page scripts do that.
// Usage: swift tools/page-data.swift design/Main.dc.html
import Foundation
import JavaScriptCore

let path = CommandLine.arguments[1]
let html = try String(contentsOfFile: path, encoding: .utf8)
guard let start = html.range(of: #"<script type="text/x-dc"[^>]*>"#, options: .regularExpression),
      let end = html.range(of: "</script>", range: start.upperBound..<html.endIndex) else {
    print("{}"); exit(0)
}
let code = String(html[start.upperBound..<end.lowerBound])
let js = JSContext()!
js.exceptionHandler = { _, e in FileHandle.standardError.write("JS error: \(e?.toString() ?? "?")\n".data(using: .utf8)!); exit(1) }
js.evaluateScript("class DCLogic { constructor() { this.state = {}; this.props = {}; } setState() {} }")
js.evaluateScript(code)
let out = js.evaluateScript("JSON.stringify(new Component().renderVals())")!.toString()!
print(out)
