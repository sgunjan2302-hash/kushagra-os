import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts

Window {
    id: root
    visible: false
    width: 430
    height: 760
    minimumWidth: 340
    minimumHeight: 440
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"
    title: "K-AI Assistant"

    property bool isHindi: kaiBackend.isHindi
    property bool showKeyModal: false
    property bool showApiKeyText: false

    Shortcut {
        sequence: "Escape"
        onActivated: {
            if (root.showKeyModal) {
                root.showKeyModal = false
            } else {
                Qt.quit()
            }
        }
    }

    palette.windowText: "#FFFFFF"
    palette.text: "#FFFFFF"
    palette.buttonText: "#FFFFFF"
    palette.button: "#1E293B"

    component GlassButton: Button {
        id: btnControl
        implicitHeight: 34
        leftPadding: 12
        rightPadding: 12
        topPadding: 6
        bottomPadding: 6
        hoverEnabled: true

        background: Rectangle {
            radius: 9
            color: {
                if (!btnControl.enabled) {
                    return btnControl.highlighted ? "#33FF9933" : "#10FFFFFF"
                }
                if (btnControl.highlighted) {
                    return btnControl.down ? "#D97706" : (btnControl.hovered ? "#FFA94D" : "#FF9933")
                }
                return btnControl.down ? "#30FFFFFF" : (btnControl.hovered ? "#24FFFFFF" : "#15FFFFFF")
            }
            border.color: {
                if (!btnControl.enabled) return "#20FFFFFF"
                if (btnControl.highlighted) return btnControl.activeFocus ? "#FFFFFF" : "#FF9933"
                return btnControl.activeFocus ? "#FF9933" : "#30FFFFFF"
            }
            border.width: 1
        }

        contentItem: Text {
            text: btnControl.text
            font.pixelSize: 12
            font.weight: btnControl.highlighted ? Font.Bold : Font.Medium
            color: {
                if (!btnControl.enabled) return "#64748B"
                return btnControl.highlighted ? "#060913" : "#F8FAFC"
            }
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    ListModel {
        id: chatModel
    }

    function findMessageIndex(msgId) {
        for (var i = chatModel.count - 1; i >= 0; i--) {
            if (chatModel.get(i).msgId === msgId) {
                return i
            }
        }
        return -1
    }

    function scrollToBottom() {
        Qt.callLater(function() {
            if (chatView.count > 0) {
                chatView.positionViewAtEnd()
            }
        })
    }

    Connections {
        target: kaiBackend

        function onMessageAdded(msg) {
            chatModel.append({
                "msgId": msg.msgId || "",
                "role": msg.role || "system",
                "msgType": msg.msgType || "chat",
                "text": msg.text || "",
                "streaming": Boolean(msg.streaming),
                "actionId": msg.actionId || "",
                "actionTitle": msg.actionTitle || "",
                "actionDesc": msg.actionDesc || "",
                "argsPretty": msg.argsPretty || "{}",
                "requiresPolkit": Boolean(msg.requiresPolkit),
                "cardStatus": msg.cardStatus || "",
                "cardOutput": msg.cardOutput || "",
                "cardOk": msg.cardOk === undefined ? true : Boolean(msg.cardOk)
            })
            root.scrollToBottom()
        }

        function onMessageUpdated(msgId, newText, streaming) {
            var idx = root.findMessageIndex(msgId)
            if (idx >= 0) {
                chatModel.setProperty(idx, "text", newText)
                chatModel.setProperty(idx, "streaming", streaming)
                root.scrollToBottom()
            }
        }

        function onActionCardUpdated(cardId, status, output, ok) {
            var idx = root.findMessageIndex(cardId)
            if (idx >= 0) {
                chatModel.setProperty(idx, "cardStatus", status)
                chatModel.setProperty(idx, "cardOutput", output)
                chatModel.setProperty(idx, "cardOk", ok)
                root.scrollToBottom()
            }
        }

        function onMessagesCleared() {
            chatModel.clear()
        }
    }

    // Main frosted-glass side drawer surface
    Rectangle {
        id: glassFrame
        anchors.fill: parent
        radius: 18
        color: "#E80B1120"
        border.color: "#38FFFFFF"
        border.width: 1
        clip: true

        // Subtle Kushagra dark-glass ambient glow
        Rectangle {
            anchors.fill: parent
            radius: 18
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#220F172A" }
                GradientStop { position: 0.5; color: "#00060913" }
                GradientStop { position: 1.0; color: "#33060913" }
            }
        }

        // Top tri-color accent hairline (Saffron / White / Emerald)
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 2.5
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "#FF9933" }
                GradientStop { position: 0.5; color: "#AAFFFFFF" }
                GradientStop { position: 1.0; color: "#138808" }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 10

            // Header bar with Wayland drag handle, language toggle, KWallet key & close
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Item {
                    Layout.fillWidth: true
                    implicitHeight: 32

                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        onPressed: root.startSystemMove()
                    }

                    RowLayout {
                        anchors.fill: parent
                        spacing: 8

                        Image {
                            source: kushagraLogoUrl
                            sourceSize.width: 24
                            sourceSize.height: 24
                            fillMode: Image.PreserveAspectFit
                            visible: status === Image.Ready
                        }

                        ColumnLayout {
                            spacing: 0
                            Text {
                                text: root.isHindi ? "K-AI सहायक" : "K-AI Assistant"
                                color: "#FFFFFF"
                                font.pixelSize: 15
                                font.weight: Font.Bold
                            }
                            Text {
                                text: isPreviewMode ? "Kushagra OS • Preview" : "Kushagra OS • Wayland"
                                color: "#94A3B8"
                                font.pixelSize: 10
                            }
                        }

                        Item { Layout.fillWidth: true }
                    }
                }

                GlassButton {
                    text: root.isHindi ? "EN" : "हिन्दी"
                    implicitHeight: 28
                    leftPadding: 10
                    rightPadding: 10
                    onClicked: kaiBackend.setHindi(!root.isHindi)
                }

                GlassButton {
                    text: root.isHindi ? "API की" : "API Key"
                    implicitHeight: 28
                    leftPadding: 10
                    rightPadding: 10
                    onClicked: root.showKeyModal = true
                }

                GlassButton {
                    text: "✕"
                    implicitWidth: 28
                    implicitHeight: 28
                    leftPadding: 0
                    rightPadding: 0
                    onClicked: Qt.quit()
                }
            }

            // Live Model Tier Badge + Engine / Idle RAM status strip
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: statusCol.implicitHeight + 16
                radius: 12
                color: "#D90F172A"
                border.color: "#2EFFFFFF"
                border.width: 1

                ColumnLayout {
                    id: statusCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 8
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        // Tier Badge
                        Rectangle {
                            radius: 8
                            implicitHeight: 24
                            implicitWidth: tierLbl.implicitWidth + 16
                            color: {
                                if (kaiBackend.tierNum === 1) return "#2238BDF8"
                                if (kaiBackend.tierNum === 2) return "#22138808"
                                if (kaiBackend.tierNum === 3) return "#22FF9933"
                                return "#22FFFFFF"
                            }
                            border.color: {
                                if (kaiBackend.tierNum === 1) return "#38BDF8"
                                if (kaiBackend.tierNum === 2) return "#22C55E"
                                if (kaiBackend.tierNum === 3) return "#FF9933"
                                return "#64748B"
                            }
                            border.width: 1

                            Text {
                                id: tierLbl
                                anchors.centerIn: parent
                                text: kaiBackend.tierBadge
                                color: "#FFFFFF"
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                            }
                        }

                        // Engine & Idle RAM Badge
                        Rectangle {
                            Layout.fillWidth: true
                            radius: 8
                            implicitHeight: 24
                            color: "#14FFFFFF"
                            border.color: kaiBackend.engineOnline ? "#4422C55E" : "#44F59E0B"
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 6

                                Rectangle {
                                    width: 7
                                    height: 7
                                    radius: 4
                                    color: kaiBackend.engineOnline ? "#22C55E" : "#F59E0B"
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: kaiBackend.engineStatusText
                                    color: "#E2E8F0"
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                }
                            }
                        }

                        GlassButton {
                            text: "↻"
                            implicitWidth: 26
                            implicitHeight: 24
                            leftPadding: 0
                            rightPadding: 0
                            onClicked: kaiBackend.refreshStatus()
                        }
                    }

                    // Hardware summary / offline engine quick action
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        visible: kaiBackend.tierDetail.length > 0 || !kaiBackend.engineOnline

                        Text {
                            Layout.fillWidth: true
                            text: kaiBackend.engineOnline
                                  ? kaiBackend.tierDetail
                                  : (root.isHindi
                                     ? "स्थानीय इंजन बंद है — 'Start' दबाएं या Cloud Key सेट करें"
                                     : "Local engine offline — start service or add Cloud API key")
                            color: kaiBackend.engineOnline ? "#94A3B8" : "#FBBF24"
                            font.pixelSize: 10
                            elide: Text.ElideRight
                        }

                        GlassButton {
                            visible: !kaiBackend.engineOnline
                            text: root.isHindi ? "शुरू करें" : "Start"
                            implicitHeight: 22
                            leftPadding: 8
                            rightPadding: 8
                            onClicked: kaiBackend.startEngineService()
                        }
                    }
                }
            }

            // Chat & Action Confirmation Card Stream
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 14
                color: "#0CFFFFFF"
                border.color: "#20FFFFFF"
                border.width: 1
                clip: true

                // Empty welcome state
                ColumnLayout {
                    anchors.centerIn: parent
                    width: parent.width - 48
                    spacing: 10
                    visible: chatModel.count === 0

                    Text {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        text: root.isHindi
                              ? "नमस्ते! मैं K-AI हूँ।"
                              : "Namaste! I am K-AI."
                        color: "#FFFFFF"
                        font.pixelSize: 17
                        font.weight: Font.Bold
                    }

                    Text {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: root.isHindi
                              ? "हिन्दी, Hinglish या English में पूछें। सिस्टम एक्शन (/dns, /layout, /health, /scan) चलाने से पहले हमेशा आपकी स्पष्ट अनुमति ली जाएगी।"
                              : "Ask in English, Hindi, or Hinglish. System commands (/dns, /layout, /health, /scan, /glass) always require your explicit Approve & Run click."
                        color: "#94A3B8"
                        font.pixelSize: 12
                    }
                }

                ListView {
                    id: chatView
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10
                    model: chatModel
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                    }

                    delegate: Item {
                        id: rowDelegate
                        width: ListView.view ? ListView.view.width : 360
                        implicitHeight: {
                            if (model.msgType === "action_card") return actionCardRect.implicitHeight
                            if (model.msgType === "notice") return noticeRect.implicitHeight
                            return bubbleRect.implicitHeight
                        }

                        // 1. Standard User / Assistant Chat Bubble
                        Rectangle {
                            id: bubbleRect
                            visible: model.msgType === "chat"
                            width: Math.min(rowDelegate.width - 14, Math.max(150, naturalWidthProbe.implicitWidth + 28))
                            anchors.right: model.role === "user" ? parent.right : undefined
                            anchors.left: model.role !== "user" ? parent.left : undefined
                            implicitHeight: msgCol.implicitHeight + 18
                            radius: 12
                            color: model.role === "user" ? "#2BFF9933" : "#18FFFFFF"
                            border.color: model.role === "user" ? "#66FF9933" : "#2DFFFFFF"
                            border.width: 1

                            Text {
                                id: naturalWidthProbe
                                visible: false
                                text: model.text
                                font.pixelSize: 13
                            }

                            ColumnLayout {
                                id: msgCol
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 9
                                spacing: 4

                                Text {
                                    text: model.role === "user"
                                          ? (root.isHindi ? "आप" : "You")
                                          : (model.streaming ? "K-AI • ..." : "K-AI")
                                    color: model.role === "user" ? "#FFBD73" : "#34D399"
                                    font.pixelSize: 10
                                    font.weight: Font.Bold
                                }

                                TextEdit {
                                    id: msgEdit
                                    Layout.fillWidth: true
                                    readOnly: true
                                    selectByMouse: true
                                    wrapMode: TextEdit.Wrap
                                    text: model.text
                                    color: "#F8FAFC"
                                    selectionColor: "#66FF9933"
                                    font.pixelSize: 13
                                }
                            }
                        }

                        // 2. System / Validation Notice
                        Rectangle {
                            id: noticeRect
                            visible: model.msgType === "notice"
                            width: rowDelegate.width
                            implicitHeight: noticeTxt.implicitHeight + 16
                            radius: 10
                            color: model.cardOk ? "#1A138808" : "#22EF4444"
                            border.color: model.cardOk ? "#5522C55E" : "#66EF4444"
                            border.width: 1

                            Text {
                                id: noticeTxt
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 8
                                wrapMode: Text.WordWrap
                                text: model.text
                                color: model.cardOk ? "#BBF7D0" : "#FECACA"
                                font.pixelSize: 11
                            }
                        }

                        // 3. Interactive Action Confirmation Card (Approve & Run / Cancel)
                        Rectangle {
                            id: actionCardRect
                            visible: model.msgType === "action_card"
                            width: rowDelegate.width
                            implicitHeight: cardCol.implicitHeight + 22
                            radius: 13
                            color: "#EB0F172A"
                            border.color: {
                                if (model.cardStatus === "completed") return "#22C55E"
                                if (model.cardStatus === "failed") return "#EF4444"
                                if (model.cardStatus === "cancelled") return "#475569"
                                return "#FF9933"
                            }
                            border.width: 1.5

                            ColumnLayout {
                                id: cardCol
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 11
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    Rectangle {
                                        radius: 6
                                        implicitHeight: 20
                                        implicitWidth: badgeLbl.implicitWidth + 12
                                        color: "#26FF9933"
                                        border.color: "#88FF9933"
                                        border.width: 1

                                        Text {
                                            id: badgeLbl
                                            anchors.centerIn: parent
                                            text: root.isHindi ? "कार्रवाई पुष्टि" : "ACTION CONFIRMATION"
                                            color: "#FFBD73"
                                            font.pixelSize: 10
                                            font.weight: Font.Bold
                                        }
                                    }

                                    Item { Layout.fillWidth: true }

                                    Rectangle {
                                        radius: 6
                                        implicitHeight: 20
                                        implicitWidth: stLbl.implicitWidth + 12
                                        color: {
                                            if (model.cardStatus === "completed") return "#2622C55E"
                                            if (model.cardStatus === "failed") return "#26EF4444"
                                            if (model.cardStatus === "running") return "#2638BDF8"
                                            if (model.cardStatus === "cancelled") return "#2264748B"
                                            return "#22F59E0B"
                                        }

                                        Text {
                                            id: stLbl
                                            anchors.centerIn: parent
                                            text: {
                                                if (model.cardStatus === "running") return root.isHindi ? "चल रहा है..." : "Running..."
                                                if (model.cardStatus === "completed") return root.isHindi ? "पूर्ण" : "Completed"
                                                if (model.cardStatus === "failed") return root.isHindi ? "विफल" : "Failed"
                                                if (model.cardStatus === "cancelled") return root.isHindi ? "रद्द" : "Cancelled"
                                                return root.isHindi ? "अनुमति प्रतीक्षित" : "Needs Approval"
                                            }
                                            color: "#F8FAFC"
                                            font.pixelSize: 10
                                            font.weight: Font.DemiBold
                                        }
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "/" + model.actionId + "  —  " + model.actionTitle
                                    color: "#FFFFFF"
                                    font.pixelSize: 13
                                    font.weight: Font.Bold
                                    wrapMode: Text.WordWrap
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: model.actionDesc
                                    color: "#CBD5E1"
                                    font.pixelSize: 11
                                    wrapMode: Text.WordWrap
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: argsTxt.implicitHeight + 12
                                    radius: 8
                                    color: "#14FFFFFF"
                                    border.color: "#22FFFFFF"

                                    TextEdit {
                                        id: argsTxt
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.margins: 6
                                        readOnly: true
                                        selectByMouse: true
                                        wrapMode: TextEdit.Wrap
                                        text: model.argsPretty
                                        color: "#E2E8F0"
                                        font.pixelSize: 11
                                        font.family: "monospace"
                                    }
                                }

                                Text {
                                    visible: model.requiresPolkit
                                    Layout.fillWidth: true
                                    text: root.isHindi
                                          ? "सुरक्षा: यह क्रिया Polkit अनुमति मांग सकती है (k-ai-broker --approved)।"
                                          : "Security: May prompt via Polkit (executed via k-ai-broker --approved)."
                                    color: "#FBBF24"
                                    font.pixelSize: 10
                                    wrapMode: Text.WordWrap
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    visible: model.cardStatus === "pending"

                                    GlassButton {
                                        Layout.fillWidth: true
                                        highlighted: true
                                        text: root.isHindi ? "स्वीकृत करें व चलाएं" : "Approve & Run"
                                        onClicked: kaiBackend.approveAction(model.msgId)
                                    }

                                    GlassButton {
                                        Layout.fillWidth: true
                                        text: root.isHindi ? "रद्द करें" : "Cancel"
                                        onClicked: kaiBackend.cancelAction(model.msgId)
                                    }
                                }

                                Rectangle {
                                    visible: model.cardOutput.length > 0
                                    Layout.fillWidth: true
                                    implicitHeight: outTxt.implicitHeight + 12
                                    radius: 8
                                    color: model.cardOk ? "#1622C55E" : "#1CEF4444"
                                    border.color: model.cardOk ? "#4422C55E" : "#55EF4444"

                                    TextEdit {
                                        id: outTxt
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.margins: 6
                                        readOnly: true
                                        selectByMouse: true
                                        wrapMode: TextEdit.Wrap
                                        text: model.cardOutput
                                        color: model.cardOk ? "#DCFCE7" : "#FEE2E2"
                                        font.pixelSize: 11
                                        font.family: "monospace"
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Quick Slash Command Chips
            Flickable {
                Layout.fillWidth: true
                implicitHeight: 28
                contentWidth: chipsRow.implicitWidth
                clip: true

                Row {
                    id: chipsRow
                    spacing: 6

                    Repeater {
                        model: ["/health", "/dns status", "/dns on", "/layout classic", "/layout floating", "/glass status", "/scan", "/convert", "/windows --dry-run"]

                        delegate: Button {
                            required property string modelData
                            implicitHeight: 26
                            leftPadding: 10
                            rightPadding: 10
                            hoverEnabled: true
                            text: modelData
                            onClicked: {
                                if (modelData !== "/scan" && modelData !== "/convert") {
                                    kaiBackend.submitMessage(modelData)
                                } else {
                                    promptInput.text = modelData + " ~/"
                                    promptInput.forceActiveFocus()
                                }
                            }
                            background: Rectangle {
                                radius: 13
                                color: parent.hovered ? "#28FF9933" : "#14FFFFFF"
                                border.color: parent.hovered ? "#FF9933" : "#2DFFFFFF"
                            }
                            contentItem: Text {
                                text: parent.text
                                color: "#E2E8F0"
                                font.pixelSize: 11
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }
            }

            // Attached Context Chip (from FollowAlong or Read Screen OCR)
            Rectangle {
                visible: kaiBackend.attachedContext.length > 0
                Layout.fillWidth: true
                implicitHeight: 32
                radius: 9
                color: "#1E138808"
                border.color: "#5522C55E"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 6
                    spacing: 8

                    Text {
                        Layout.fillWidth: true
                        text: (root.isHindi ? "संलग्न संदर्भ: " : "Context: ")
                              + kaiBackend.attachedContext.replace(/\n/g, " ")
                        color: "#BBF7D0"
                        font.pixelSize: 11
                        elide: Text.ElideRight
                    }

                    GlassButton {
                        text: "✕"
                        implicitWidth: 24
                        implicitHeight: 22
                        leftPadding: 0
                        rightPadding: 0
                        onClicked: kaiBackend.clearContext()
                    }
                }
            }

            // Input TextArea Dock
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Math.min(110, Math.max(54, promptInput.contentHeight + 16))
                radius: 12
                color: "#16FFFFFF"
                border.color: promptInput.activeFocus ? "#FF9933" : "#32FFFFFF"
                border.width: 1

                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 8
                    clip: true

                    TextArea {
                        id: promptInput
                        placeholderText: root.isHindi
                            ? "संदेश लिखें या /health, /dns, /layout कमांड दें..."
                            : "Ask in English / Hindi / Hinglish, or type /health, /dns, /layout..."
                        placeholderTextColor: "#64748B"
                        color: "#FFFFFF"
                        font.pixelSize: 13
                        wrapMode: TextArea.Wrap
                        background: Item {}

                        Keys.onPressed: function(event) {
                            if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                                    && !(event.modifiers & Qt.ShiftModifier)) {
                                event.accepted = true
                                var txt = promptInput.text
                                promptInput.text = ""
                                kaiBackend.submitMessage(txt)
                            }
                        }
                    }
                }
            }

            // Bottom Action Toolbar: User-Triggered Read Screen (OCR) + Clear + Send
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                GlassButton {
                    enabled: !kaiBackend.ocrBusy
                    text: kaiBackend.ocrBusy
                          ? (root.isHindi ? "OCR जारी..." : "Reading...")
                          : (root.isHindi ? "स्क्रीन पढ़ें (OCR)" : "Read Screen (OCR)")
                    onClicked: kaiBackend.triggerOcr()
                }

                GlassButton {
                    text: root.isHindi ? "साफ़ करें" : "Clear"
                    onClicked: kaiBackend.clearChat()
                }

                Item { Layout.fillWidth: true }

                GlassButton {
                    visible: kaiBackend.chatBusy
                    text: root.isHindi ? "रोकें" : "Stop"
                    onClicked: kaiBackend.stopGeneration()
                }

                GlassButton {
                    visible: !kaiBackend.chatBusy
                    highlighted: true
                    enabled: promptInput.text.trim().length > 0 || kaiBackend.attachedContext.length > 0
                    text: root.isHindi ? "भेजें" : "Send"
                    onClicked: {
                        var txt = promptInput.text
                        promptInput.text = ""
                        kaiBackend.submitMessage(txt)
                    }
                }
            }
        }
    }

    // Modal Dialog: KWallet Cloud API Key Settings (`k-ai-engine set-key`)
    Rectangle {
        id: keyModalOverlay
        visible: root.showKeyModal
        anchors.fill: parent
        z: 50
        radius: 18
        color: "#B8040711"

        MouseArea {
            anchors.fill: parent
            onClicked: {}
        }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 28, 370)
            implicitHeight: modalCol.implicitHeight + 28
            radius: 16
            color: "#F50B1120"
            border.color: "#55FF9933"
            border.width: 1.5

            ColumnLayout {
                id: modalCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 14
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: root.isHindi ? "क्लाउड API की (KWallet)" : "Cloud API Key (KWallet)"
                        color: "#FFFFFF"
                        font.pixelSize: 15
                        font.weight: Font.Bold
                    }
                    GlassButton {
                        text: "✕"
                        implicitWidth: 26
                        implicitHeight: 26
                        leftPadding: 0
                        rightPadding: 0
                        onClicked: root.showKeyModal = false
                    }
                }

                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: root.isHindi
                          ? "आपकी API की `k-ai-engine set-key` के माध्यम से सीधे KDE Wallet (KWallet) में सुरक्षित रखी जाती है — कभी प्लेन-टेक्स्ट फ़ाइल या Git में नहीं।"
                          : "Your key is stored strictly in KDE Wallet (KWallet) via `k-ai-engine set-key` — never saved to config files or Git."
                    color: "#94A3B8"
                    font.pixelSize: 11
                }

                ComboBox {
                    id: providerBox
                    Layout.fillWidth: true
                    model: ["openai", "groq", "gemini", "custom"]
                    background: Rectangle {
                        radius: 8
                        color: "#18FFFFFF"
                        border.color: "#38FFFFFF"
                    }
                    contentItem: Text {
                        leftPadding: 10
                        text: providerBox.displayText
                        color: "#FFFFFF"
                        font.pixelSize: 12
                        verticalAlignment: Text.AlignVCenter
                    }
                    delegate: ItemDelegate {
                        required property string modelData
                        required property int index
                        width: providerBox.width
                        height: 32
                        highlighted: providerBox.highlightedIndex === index
                        contentItem: Text {
                            text: modelData
                            color: highlighted ? "#FFBD73" : "#FFFFFF"
                            font.pixelSize: 12
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            color: highlighted ? "#26FF9933" : "transparent"
                        }
                    }
                    popup: Popup {
                        y: providerBox.height + 4
                        width: providerBox.width
                        implicitHeight: contentItem.implicitHeight + 8
                        padding: 4
                        contentItem: ListView {
                            clip: true
                            implicitHeight: contentHeight
                            model: providerBox.popup.visible ? providerBox.delegateModel : null
                            currentIndex: providerBox.highlightedIndex
                        }
                        background: Rectangle {
                            radius: 10
                            color: "#F20F172A"
                            border.color: "#44FFFFFF"
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    visible: providerBox.currentText === "custom"

                    TextField {
                        id: baseUrlInput
                        Layout.fillWidth: true
                        placeholderText: "https://api.example.com/v1"
                        placeholderTextColor: "#64748B"
                        color: "#FFFFFF"
                        font.pixelSize: 12
                        background: Rectangle {
                            radius: 8
                            color: "#18FFFFFF"
                            border.color: baseUrlInput.activeFocus ? "#FF9933" : "#38FFFFFF"
                        }
                    }

                    TextField {
                        id: cloudModelInput
                        Layout.preferredWidth: 120
                        placeholderText: "Model ID"
                        placeholderTextColor: "#64748B"
                        color: "#FFFFFF"
                        font.pixelSize: 12
                        background: Rectangle {
                            radius: 8
                            color: "#18FFFFFF"
                            border.color: cloudModelInput.activeFocus ? "#FF9933" : "#38FFFFFF"
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    TextField {
                        id: apiKeyInput
                        Layout.fillWidth: true
                        echoMode: root.showApiKeyText ? TextInput.Normal : TextInput.Password
                        placeholderText: root.isHindi ? "API की पेस्ट करें..." : "Paste API key..."
                        placeholderTextColor: "#64748B"
                        color: "#FFFFFF"
                        font.pixelSize: 12
                        background: Rectangle {
                            radius: 8
                            color: "#18FFFFFF"
                            border.color: apiKeyInput.activeFocus ? "#FF9933" : "#38FFFFFF"
                        }
                    }

                    GlassButton {
                        text: root.showApiKeyText ? "Hide" : "Show"
                        implicitHeight: 34
                        onClicked: root.showApiKeyText = !root.showApiKeyText
                    }
                }

                Text {
                    visible: kaiBackend.keyFeedback.length > 0
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: kaiBackend.keyFeedback
                    color: kaiBackend.keyFeedbackOk ? "#4ADE80" : "#F87171"
                    font.pixelSize: 11
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    GlassButton {
                        Layout.fillWidth: true
                        text: root.isHindi ? "बंद करें" : "Close"
                        onClicked: root.showKeyModal = false
                    }

                    GlassButton {
                        Layout.fillWidth: true
                        highlighted: true
                        enabled: !kaiBackend.keyBusy && apiKeyInput.text.trim().length > 0
                        text: kaiBackend.keyBusy
                              ? (root.isHindi ? "सहेजा जा रहा..." : "Saving...")
                              : (root.isHindi ? "KWallet में सहेजें" : "Save to KWallet")
                        onClicked: {
                            var secret = apiKeyInput.text
                            apiKeyInput.text = ""
                            kaiBackend.saveApiKey(
                                providerBox.currentText,
                                secret,
                                providerBox.currentText === "custom" ? baseUrlInput.text : "",
                                providerBox.currentText === "custom" ? cloudModelInput.text : ""
                            )
                        }
                    }
                }
            }
        }
    }
}
