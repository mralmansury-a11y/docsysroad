document.addEventListener("DOMContentLoaded", function () {
    // زر فتح/إغلاق القائمة الجانبية للجوال
    const toggle = document.getElementById("sidebarToggle");
    const sidebar = document.querySelector(".sidebar");
    if (toggle && sidebar) {
        toggle.addEventListener("click", () => sidebar.classList.toggle("show"));
    }

    // منطقة السحب والإفلات لرفع الملف
    const dropZone = document.getElementById("uploadDrop");
    const fileInput = document.getElementById("fileInput");
    const fileNameLabel = document.getElementById("fileNameLabel");

    if (dropZone && fileInput) {
        dropZone.addEventListener("click", () => fileInput.click());

        ["dragenter", "dragover"].forEach(evt =>
            dropZone.addEventListener(evt, (e) => {
                e.preventDefault();
                dropZone.classList.add("dragover");
            })
        );
        ["dragleave", "drop"].forEach(evt =>
            dropZone.addEventListener(evt, (e) => {
                e.preventDefault();
                dropZone.classList.remove("dragover");
            })
        );
        dropZone.addEventListener("drop", (e) => {
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                updateFileName();
            }
        });
        fileInput.addEventListener("change", updateFileName);

        function updateFileName() {
            if (fileInput.files.length && fileNameLabel) {
                fileNameLabel.textContent = "الملف المختار: " + fileInput.files[0].name;
                fileNameLabel.classList.remove("d-none");
                document.getElementById("uploadDropText")?.classList.add("d-none");
            }
        }
    }

    // إظهار/إخفاء حقول المُرسَل إليه حسب النوع المختار + تحميل القوائم من API
    const recipientTypeSelect = document.getElementById("recipientType");
    const recipientSelectWrap = document.getElementById("recipientSelectWrap");
    const recipientTextWrap = document.getElementById("recipientTextWrap");
    const recipientSelect = document.getElementById("recipientSelect");

    if (recipientTypeSelect) {
        recipientTypeSelect.addEventListener("change", async function () {
            const val = this.value;
            if (val === "external") {
                recipientSelectWrap.classList.add("d-none");
                recipientTextWrap.classList.remove("d-none");
                recipientSelect.removeAttribute("required");
            } else if (val === "department" || val === "user") {
                recipientTextWrap.classList.add("d-none");
                recipientSelectWrap.classList.remove("d-none");
                recipientSelect.setAttribute("required", "required");

                const res = await fetch(`/documents/api/recipients?type=${val}`);
                const items = await res.json();
                recipientSelect.innerHTML = '<option value="">-- اختر --</option>';
                items.forEach(item => {
                    const opt = document.createElement("option");
                    opt.value = item.id;
                    opt.textContent = item.name;
                    recipientSelect.appendChild(opt);
                });
            } else {
                recipientSelectWrap.classList.add("d-none");
                recipientTextWrap.classList.add("d-none");
            }
        });
    }

    // تفعيل/تعطيل زر "إصدار" حسب اكتمال الحقول (FR-2.3)
    const issueForm = document.getElementById("issueForm");
    if (issueForm) {
        const submitBtn = document.getElementById("issueSubmitBtn");
        const requiredFields = issueForm.querySelectorAll("[data-required-check]");
        function checkComplete() {
            let complete = fileInput && fileInput.files.length > 0;
            requiredFields.forEach(f => {
                if (!f.value || f.value.trim() === "") complete = false;
            });
            submitBtn.disabled = !complete;
        }
        requiredFields.forEach(f => f.addEventListener("input", checkComplete));
        requiredFields.forEach(f => f.addEventListener("change", checkComplete));
        if (fileInput) fileInput.addEventListener("change", checkComplete);
        checkComplete();
    }

    // إغلاق تلقائي لرسائل التنبيه
    document.querySelectorAll(".alert").forEach(alertEl => {
        setTimeout(() => {
            try { bootstrap.Alert.getOrCreateInstance(alertEl).close(); } catch (e) {}
        }, 6000);
    });
});
