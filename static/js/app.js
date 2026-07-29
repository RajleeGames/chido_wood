"use strict";


const SIDEBAR_BREAKPOINT = 820;
const SIDEBAR_STORAGE_KEY = "chido-sidebar-collapsed";


function isDesktopLayout() {
    return window.innerWidth > SIDEBAR_BREAKPOINT;
}


function getStoredSidebarState() {
    try {
        return (
            localStorage.getItem(SIDEBAR_STORAGE_KEY)
            === "true"
        );
    } catch (error) {
        return false;
    }
}


function storeSidebarState(isCollapsed) {
    try {
        localStorage.setItem(
            SIDEBAR_STORAGE_KEY,
            String(isCollapsed)
        );
    } catch (error) {
        // Sidebar still works even if browser storage is unavailable.
    }
}


function showPageLoader(message = "Loading") {
    const loader = document.getElementById("pageLoader");

    if (!loader) {
        return;
    }

    const loaderText = loader.querySelector(
        "[data-loader-text]"
    );

    if (loaderText) {
        loaderText.textContent = message;
    }

    loader.classList.add("is-visible");
    loader.setAttribute("aria-hidden", "false");
}


function hidePageLoader() {
    const loader = document.getElementById("pageLoader");

    if (!loader) {
        return;
    }

    loader.classList.remove("is-visible");
    loader.setAttribute("aria-hidden", "true");
}


function initializePageLoader() {
    window.addEventListener("load", () => {
        window.setTimeout(() => {
            hidePageLoader();
        }, 120);
    });

    window.addEventListener("pageshow", () => {
        hidePageLoader();
    });

    document.addEventListener("submit", (event) => {
        const form = event.target;

        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        /*
         * A page-specific handler may cancel the submission first,
         * for example when an SMS confirmation is rejected.
         * Do not show a loader for a cancelled submission.
         */
        if (event.defaultPrevented) {
            return;
        }

        if (
            form.hasAttribute("data-no-loader")
            || form.target === "_blank"
        ) {
            return;
        }

        const loadingMessage = (
            form.dataset.loadingMessage
            || "Saving"
        );

        showPageLoader(loadingMessage);
    });

    document.addEventListener("click", (event) => {
        const link = event.target.closest("a");

        if (!link) {
            return;
        }

        if (
            event.defaultPrevented
            || event.button !== 0
            || event.ctrlKey
            || event.metaKey
            || event.shiftKey
            || event.altKey
        ) {
            return;
        }

        if (
            link.hasAttribute("download")
            || link.target === "_blank"
            || link.hasAttribute("data-no-loader")
        ) {
            return;
        }

        const rawHref = link.getAttribute("href");

        if (
            !rawHref
            || rawHref === "#"
            || rawHref.startsWith("javascript:")
            || rawHref.startsWith("mailto:")
            || rawHref.startsWith("tel:")
        ) {
            return;
        }

        const destination = new URL(
            link.href,
            window.location.href
        );

        if (destination.origin !== window.location.origin) {
            return;
        }

        const samePageAnchor = (
            destination.pathname === window.location.pathname
            && destination.search === window.location.search
            && destination.hash
        );

        if (samePageAnchor) {
            return;
        }

        showPageLoader("Loading");
    });
}


function openModal(modalId) {
    const modal = document.getElementById(modalId);

    if (!modal) {
        return;
    }

    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
}


function closeModal(modal) {
    if (!modal) {
        return;
    }

    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");

    const remainingOpenModals = document.querySelectorAll(
        ".app-modal.open"
    );

    if (remainingOpenModals.length === 0) {
        document.body.classList.remove("modal-open");
    }
}


function initializeSidebar() {
    const sidebar = document.getElementById("sidebar");

    const overlay = document.querySelector(
        "[data-sidebar-overlay]"
    );

    const toggleButtons = document.querySelectorAll(
        "[data-sidebar-toggle]"
    );

    const oldOpenButtons = document.querySelectorAll(
        "[data-sidebar-open]"
    );

    const closeButtons = document.querySelectorAll(
        "[data-sidebar-close]"
    );

    if (!sidebar || !overlay) {
        document.documentElement.classList.remove(
            "sidebar-collapsed-preload"
        );

        return;
    }

    function updateToggleState(isExpanded) {
        toggleButtons.forEach((button) => {
            button.setAttribute(
                "aria-expanded",
                String(isExpanded)
            );
        });

        oldOpenButtons.forEach((button) => {
            button.setAttribute(
                "aria-expanded",
                String(isExpanded)
            );
        });
    }

    function openMobileSidebar() {
        sidebar.classList.add("open");
        overlay.classList.add("open");
        updateToggleState(true);
    }

    function closeMobileSidebar() {
        sidebar.classList.remove("open");
        overlay.classList.remove("open");
        updateToggleState(false);
    }

    function applyDesktopSidebarState(isCollapsed) {
        document.body.classList.toggle(
            "sidebar-collapsed",
            isCollapsed
        );

        sidebar.classList.remove("open");
        overlay.classList.remove("open");

        updateToggleState(!isCollapsed);
    }

    function toggleSidebar() {
        if (isDesktopLayout()) {
            const isCurrentlyCollapsed = (
                document.body.classList.contains(
                    "sidebar-collapsed"
                )
            );

            const newCollapsedState = (
                !isCurrentlyCollapsed
            );

            applyDesktopSidebarState(
                newCollapsedState
            );

            storeSidebarState(
                newCollapsedState
            );

            return;
        }

        if (sidebar.classList.contains("open")) {
            closeMobileSidebar();
        } else {
            openMobileSidebar();
        }
    }

    function synchronizeSidebar() {
        if (isDesktopLayout()) {
            applyDesktopSidebarState(
                getStoredSidebarState()
            );
        } else {
            document.body.classList.remove(
                "sidebar-collapsed"
            );

            closeMobileSidebar();
        }

        document.documentElement.classList.remove(
            "sidebar-collapsed-preload"
        );
    }

    toggleButtons.forEach((button) => {
        button.addEventListener(
            "click",
            toggleSidebar
        );
    });

    oldOpenButtons.forEach((button) => {
        button.addEventListener(
            "click",
            toggleSidebar
        );
    });

    closeButtons.forEach((button) => {
        button.addEventListener(
            "click",
            closeMobileSidebar
        );
    });

    overlay.addEventListener(
        "click",
        closeMobileSidebar
    );

    window.addEventListener(
        "resize",
        synchronizeSidebar
    );

    synchronizeSidebar();
}


function initializeModals() {
    const closeButtons = document.querySelectorAll(
        "[data-modal-close]"
    );

    closeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const modal = button.closest(
                ".app-modal"
            );

            closeModal(modal);
        });
    });

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") {
            return;
        }

        const openModalElement = document.querySelector(
            ".app-modal.open"
        );

        closeModal(openModalElement);
    });
}


function initializePasswordToggles() {
    const toggleButtons = document.querySelectorAll(
        "[data-password-toggle]"
    );

    toggleButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const wrapper = button.closest(
                ".password-control"
            );

            if (!wrapper) {
                return;
            }

            const input = wrapper.querySelector(
                "input"
            );

            if (!input) {
                return;
            }

            const passwordIsHidden = (
                input.type === "password"
            );

            input.type = passwordIsHidden
                ? "text"
                : "password";

            button.textContent = passwordIsHidden
                ? "Hide"
                : "Show";
        });
    });
}


function initializePasswordGenerator() {
    const generateButtons = document.querySelectorAll(
        "[data-generate-password]"
    );

    if (!generateButtons.length) {
        return;
    }

    const characterGroups = {
        uppercase: "ABCDEFGHJKLMNPQRSTUVWXYZ",
        lowercase: "abcdefghijkmnopqrstuvwxyz",
        numbers: "23456789",
        symbols: "!@#$%&*+-_=",
    };

    const allCharacters = Object.values(
        characterGroups
    ).join("");

    function secureRandomIndex(maximum) {
        if (
            window.crypto
            && window.crypto.getRandomValues
        ) {
            const values = new Uint32Array(1);
            window.crypto.getRandomValues(values);
            return values[0] % maximum;
        }

        return Math.floor(
            Math.random() * maximum
        );
    }

    function randomCharacter(characters) {
        return characters[
            secureRandomIndex(characters.length)
        ];
    }

    function shuffleCharacters(characters) {
        const result = [...characters];

        for (
            let index = result.length - 1;
            index > 0;
            index -= 1
        ) {
            const randomIndex = secureRandomIndex(
                index + 1
            );

            [
                result[index],
                result[randomIndex],
            ] = [
                result[randomIndex],
                result[index],
            ];
        }

        return result.join("");
    }

    function createPassword(length = 14) {
        const passwordCharacters = [
            randomCharacter(characterGroups.uppercase),
            randomCharacter(characterGroups.lowercase),
            randomCharacter(characterGroups.numbers),
            randomCharacter(characterGroups.symbols),
        ];

        while (passwordCharacters.length < length) {
            passwordCharacters.push(
                randomCharacter(allCharacters)
            );
        }

        return shuffleCharacters(
            passwordCharacters
        );
    }

    async function copyText(value) {
        if (
            navigator.clipboard
            && window.isSecureContext
        ) {
            await navigator.clipboard.writeText(
                value
            );
            return;
        }

        const temporaryInput = document.createElement(
            "textarea"
        );

        temporaryInput.value = value;
        temporaryInput.setAttribute(
            "readonly",
            ""
        );
        temporaryInput.style.position = "fixed";
        temporaryInput.style.opacity = "0";

        document.body.appendChild(
            temporaryInput
        );

        temporaryInput.select();
        document.execCommand("copy");
        temporaryInput.remove();
    }

    generateButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const form = button.closest("form");

            if (!form) {
                return;
            }

            const password = createPassword();

            const primaryInput = form.querySelector(
                '[data-generated-password-target="primary"]'
            );

            const confirmationInput = form.querySelector(
                '[data-generated-password-target="confirmation"]'
            );

            if (primaryInput) {
                primaryInput.value = password;
                primaryInput.dispatchEvent(
                    new Event("input", {
                        bubbles: true,
                    })
                );
            }

            if (confirmationInput) {
                confirmationInput.value = password;
                confirmationInput.dispatchEvent(
                    new Event("input", {
                        bubbles: true,
                    })
                );
            }

            const displayBox = form.querySelector(
                "[data-generated-password-box]"
            );

            const displayValue = form.querySelector(
                "[data-generated-password-value]"
            );

            if (displayValue) {
                displayValue.textContent = password;
            }

            if (displayBox) {
                displayBox.hidden = false;
            }
        });
    });

    document
        .querySelectorAll(
            "[data-copy-generated-password]"
        )
        .forEach((button) => {
            button.addEventListener(
                "click",
                async () => {
                    const form = button.closest("form");

                    if (!form) {
                        return;
                    }

                    const valueElement = form.querySelector(
                        "[data-generated-password-value]"
                    );

                    const value = valueElement
                        ? valueElement.textContent.trim()
                        : "";

                    if (!value) {
                        return;
                    }

                    try {
                        await copyText(value);
                        button.textContent = "Copied";

                        window.setTimeout(() => {
                            button.textContent = "Copy";
                        }, 1400);
                    } catch (error) {
                        console.error(
                            "Unable to copy the generated password.",
                            error
                        );
                    }
                }
            );
        });
}


function initializeMessages() {
    const closeButtons = document.querySelectorAll(
        "[data-message-close]"
    );

    closeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const message = button.closest(
                ".message"
            );

            if (message) {
                message.remove();
            }
        });
    });
}


document.addEventListener("DOMContentLoaded", () => {
    initializePageLoader();
    initializeSidebar();
    initializeModals();
    initializePasswordToggles();
    initializePasswordGenerator();
    initializeMessages();
    initializeDashboardCharts();
});


window.openModal = openModal;
window.closeModal = closeModal;
window.showPageLoader = showPageLoader;
window.hidePageLoader = hidePageLoader;


function initializeDashboardCharts() {
    const dataElement = document.getElementById(
        "dashboard-chart-data"
    );

    if (!dataElement) {
        return;
    }

    const financialCanvas = document.getElementById(
        "financialTrendChart"
    );

    const incomeCanvas = document.getElementById(
        "incomeMixChart"
    );

    const financialEmpty = document.getElementById(
        "financialTrendEmpty"
    );

    if (typeof window.Chart === "undefined") {
        console.error(
            "Chart.js did not load. Check the internet connection or CDN script."
        );

        if (financialCanvas) {
            financialCanvas.hidden = true;
        }

        if (financialEmpty) {
            financialEmpty.hidden = false;
            financialEmpty.textContent = (
                "Charts could not load. Check the internet connection and refresh the page."
            );
        }

        return;
    }

    let dashboardData;

    try {
        dashboardData = JSON.parse(
            dataElement.textContent
        );
    } catch (error) {
        console.error(
            "Unable to read dashboard chart data.",
            error
        );

        if (financialCanvas) {
            financialCanvas.hidden = true;
        }

        if (financialEmpty) {
            financialEmpty.hidden = false;
            financialEmpty.textContent = (
                "Dashboard data could not be read."
            );
        }

        return;
    }

    const rootStyles = getComputedStyle(
        document.documentElement
    );

    function cssVariable(name, fallback) {
        return (
            rootStyles
                .getPropertyValue(name)
                .trim()
            || fallback
        );
    }

    const palette = {
        primary: cssVariable(
            "--primary",
            "#81532b"
        ),
        success: cssVariable(
            "--success",
            "#15803d"
        ),
        danger: cssVariable(
            "--danger",
            "#b91c1c"
        ),
        warning: cssVariable(
            "--warning",
            "#b45309"
        ),
        muted: cssVariable(
            "--muted",
            "#6b7280"
        ),
        border: cssVariable(
            "--border",
            "#e5e7eb"
        ),
        surface: cssVariable(
            "--surface",
            "#ffffff"
        ),
    };

    function hexToRgba(color, alpha) {
        const value = String(color || "").trim();

        if (!value.startsWith("#")) {
            return value;
        }

        let hex = value.slice(1);

        if (hex.length === 3) {
            hex = hex
                .split("")
                .map((character) => character + character)
                .join("");
        }

        if (hex.length !== 6) {
            return value;
        }

        const red = parseInt(hex.slice(0, 2), 16);
        const green = parseInt(hex.slice(2, 4), 16);
        const blue = parseInt(hex.slice(4, 6), 16);

        return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
    }

    const currencyFormatter = new Intl.NumberFormat(
        "en-US",
        {
            maximumFractionDigits: 0,
        }
    );

    const compactFormatter = new Intl.NumberFormat(
        "en-US",
        {
            notation: "compact",
            maximumFractionDigits: 1,
        }
    );

    function moneyLabel(value) {
        return `TZS ${currencyFormatter.format(
            Number(value) || 0
        )}`;
    }

    function normaliseValues(values, length) {
        const source = Array.isArray(values)
            ? values
            : [];

        return Array.from(
            { length },
            (_, index) => Number(source[index]) || 0
        );
    }

    window.Chart.defaults.font.family = (
        "Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    );

    window.Chart.defaults.color = palette.muted;

    const trend = dashboardData.trend || {};

    const labels = Array.isArray(trend.labels)
        ? trend.labels
        : [];

    const safeLabels = labels.length
        ? labels
        : ["No data"];

    const salesValues = normaliseValues(
        trend.sales,
        safeLabels.length
    );

    const grossProfitValues = normaliseValues(
        trend.gross_profit,
        safeLabels.length
    );

    const expenseValues = normaliseValues(
        trend.expenses,
        safeLabels.length
    );

    const netProfitValues = normaliseValues(
        trend.net_profit,
        safeLabels.length
    );

    if (financialCanvas) {
        financialCanvas.hidden = false;

        if (financialEmpty) {
            financialEmpty.hidden = true;
        }

        const existingFinancialChart = (
            window.Chart.getChart(financialCanvas)
        );

        if (existingFinancialChart) {
            existingFinancialChart.destroy();
        }

        new window.Chart(
            financialCanvas,
            {
                type: "line",
                data: {
                    labels: safeLabels,
                    datasets: [
                        {
                            label: "Sales",
                            data: salesValues,
                            borderColor: palette.primary,
                            backgroundColor: hexToRgba(
                                palette.primary,
                                0.12
                            ),
                            fill: true,
                            borderWidth: 2.2,
                            tension: 0.34,
                            pointRadius: safeLabels.length <= 14
                                ? 2.5
                                : 0,
                            pointHoverRadius: 4,
                        },
                        {
                            label: "Gross profit",
                            data: grossProfitValues,
                            borderColor: palette.success,
                            backgroundColor: palette.success,
                            fill: false,
                            borderWidth: 2,
                            tension: 0.34,
                            pointRadius: safeLabels.length <= 14
                                ? 2.2
                                : 0,
                            pointHoverRadius: 4,
                        },
                        {
                            label: "Expenses",
                            data: expenseValues,
                            borderColor: palette.danger,
                            backgroundColor: palette.danger,
                            fill: false,
                            borderWidth: 2,
                            tension: 0.34,
                            pointRadius: safeLabels.length <= 14
                                ? 2.2
                                : 0,
                            pointHoverRadius: 4,
                        },
                        {
                            label: "Net result",
                            data: netProfitValues,
                            borderColor: palette.warning,
                            backgroundColor: palette.warning,
                            fill: false,
                            borderWidth: 2,
                            tension: 0.34,
                            pointRadius: safeLabels.length <= 14
                                ? 2.2
                                : 0,
                            pointHoverRadius: 4,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    resizeDelay: 120,
                    interaction: {
                        mode: "index",
                        intersect: false,
                    },
                    animation: {
                        duration: 450,
                    },
                    plugins: {
                        legend: {
                            display: false,
                        },
                        tooltip: {
                            backgroundColor: "#111827",
                            titleColor: "#ffffff",
                            bodyColor: "#ffffff",
                            padding: 10,
                            displayColors: true,
                            callbacks: {
                                label(context) {
                                    return (
                                        `${context.dataset.label}: `
                                        + moneyLabel(context.parsed.y)
                                    );
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false,
                            },
                            border: {
                                display: false,
                            },
                            ticks: {
                                maxRotation: 0,
                                autoSkip: true,
                                maxTicksLimit: 8,
                                font: {
                                    size: 9,
                                },
                            },
                        },
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: hexToRgba(
                                    palette.border,
                                    0.82
                                ),
                            },
                            border: {
                                display: false,
                            },
                            ticks: {
                                padding: 7,
                                font: {
                                    size: 9,
                                },
                                callback(value) {
                                    return compactFormatter.format(
                                        Number(value) || 0
                                    );
                                },
                            },
                        },
                    },
                },
            }
        );
    }

    const incomeMix = dashboardData.income_mix || {};

    const salesIncome = Math.max(
        Number(incomeMix.sales) || 0,
        0
    );

    const cuttingIncome = Math.max(
        Number(incomeMix.cutting) || 0,
        0
    );

    const hasIncome = (
        salesIncome + cuttingIncome
    ) > 0;

    if (incomeCanvas) {
        const existingIncomeChart = (
            window.Chart.getChart(incomeCanvas)
        );

        if (existingIncomeChart) {
            existingIncomeChart.destroy();
        }

        new window.Chart(
            incomeCanvas,
            {
                type: "doughnut",
                data: {
                    labels: hasIncome
                        ? ["Product sales", "Cutting income"]
                        : ["No income recorded"],
                    datasets: [
                        {
                            data: hasIncome
                                ? [salesIncome, cuttingIncome]
                                : [1],
                            backgroundColor: hasIncome
                                ? [palette.primary, palette.warning]
                                : [palette.border],
                            borderColor: palette.surface,
                            borderWidth: 3,
                            hoverOffset: hasIncome ? 5 : 0,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    resizeDelay: 120,
                    cutout: "72%",
                    animation: {
                        duration: 450,
                    },
                    plugins: {
                        legend: {
                            display: false,
                        },
                        tooltip: {
                            enabled: hasIncome,
                            backgroundColor: "#111827",
                            titleColor: "#ffffff",
                            bodyColor: "#ffffff",
                            padding: 10,
                            callbacks: {
                                label(context) {
                                    return (
                                        `${context.label}: `
                                        + moneyLabel(context.parsed)
                                    );
                                },
                            },
                        },
                    },
                },
            }
        );
    }

    document
        .querySelectorAll("[data-dashboard-bar]")
        .forEach((bar) => {
            const rawValue = Number(
                bar.dataset.dashboardBar
            );

            const percentage = Math.min(
                Math.max(
                    Number.isFinite(rawValue)
                        ? rawValue
                        : 0,
                    0
                ),
                100
            );

            bar.style.setProperty(
                "--dashboard-bar-width",
                `${percentage}%`
            );
        });

    window.dashboardMoneyFormatter = moneyLabel;
}


(function initializeSMSCenter() {
    const GSM_BASIC = new Set(
        "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?" +
        "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
    );
    const GSM_EXTENDED = new Set("^{}\\[~]|€");

    function analyzeMessage(value) {
        const text = String(value || "");
        let septets = 0;
        let isUnicode = false;

        for (const character of text) {
            if (GSM_BASIC.has(character)) {
                septets += 1;
            } else if (GSM_EXTENDED.has(character)) {
                septets += 2;
            } else {
                isUnicode = true;
                break;
            }
        }

        if (!isUnicode) {
            return {
                characters: text.length,
                encoding: "GSM7",
                parts: Math.max(1, septets <= 160 ? 1 : Math.ceil(septets / 153)),
            };
        }

        return {
            characters: text.length,
            encoding: "Unicode",
            parts: Math.max(1, text.length <= 70 ? 1 : Math.ceil(text.length / 67)),
        };
    }

    function escapeRegularExpression(value) {
        return String(value).replace(
            /[.*+?^${}()|[\]\\]/g,
            "\\$&"
        );
    }

    function replaceAliases(message, aliases, value) {
        let output = String(message || "");

        aliases
            .slice()
            .sort((left, right) => right.length - left.length)
            .forEach((alias) => {
                output = output.replace(
                    new RegExp(
                        escapeRegularExpression(alias),
                        "gi"
                    ),
                    value
                );
            });

        return output;
    }

    function renderExample(message) {
        const replacements = [
            {
                aliases: [
                    "{name}",
                    "{{name}}",
                    "{{ name }}",
                    "[name]",
                ],
                value: "Asha Mushi",
            },
            {
                aliases: [
                    "{first_name}",
                    "{{first_name}}",
                    "{{ first_name }}",
                    "[first_name]",
                ],
                value: "Asha",
            },
            {
                aliases: [
                    "{phone}",
                    "{{phone}}",
                    "{{ phone }}",
                    "[phone]",
                ],
                value: "255712345678",
            },
            {
                aliases: [
                    "{company}",
                    "{{company}}",
                    "{{ company }}",
                    "[company]",
                ],
                value: "CHIDO Wood Company LTD",
            },
            {
                aliases: [
                    "{amount}",
                    "{{amount}}",
                    "{{ amount }}",
                    "[amount]",
                ],
                value: "250,000",
            },
            {
                aliases: [
                    "{balance}",
                    "{{balance}}",
                    "{{ balance }}",
                    "[balance]",
                ],
                value: "50,000",
            },
            {
                aliases: [
                    "{receipt}",
                    "{{receipt}}",
                    "{{ receipt }}",
                    "[receipt]",
                ],
                value: "SAL-000123",
            },
            {
                aliases: [
                    "{date}",
                    "{{date}}",
                    "{{ date }}",
                    "[date]",
                ],
                value: "27/07/2026",
            },
        ];

        let output = String(message || "").trim();

        replacements.forEach(({ aliases, value }) => {
            output = replaceAliases(
                output,
                aliases,
                value
            );
        });

        return (
            output
            || "Write your message to see a preview."
        );
    }

    function updateMessagePreview(input) {
        if (!input) {
            return;
        }

        const analysis = analyzeMessage(input.value);
        document.querySelectorAll("[data-sms-preview]").forEach((element) => {
            element.textContent = renderExample(input.value);
        });
        document.querySelectorAll("[data-sms-characters]").forEach((element) => {
            element.textContent = String(analysis.characters);
        });
        document.querySelectorAll("[data-sms-encoding]").forEach((element) => {
            element.textContent = analysis.encoding;
        });
        document.querySelectorAll("[data-sms-parts]").forEach((element) => {
            element.textContent = String(analysis.parts);
        });
    }

    function initializeMessagePreview() {
        const input = document.querySelector("[data-sms-message-input]");
        if (!input) {
            return;
        }

        updateMessagePreview(input);
        input.addEventListener("input", () => updateMessagePreview(input));
    }

    function initializeTemplateSelection() {
        const templateSelect = document.getElementById("id_template");
        const messageInput = document.getElementById("id_message");
        const languageSelect = document.getElementById("id_language");
        const dataElement = document.getElementById("sms-template-data");

        if (!templateSelect || !messageInput || !dataElement) {
            return;
        }

        let templateData = {};
        try {
            templateData = JSON.parse(dataElement.textContent || "{}");
        } catch (error) {
            templateData = {};
        }

        templateSelect.addEventListener("change", () => {
            const selected = templateData[String(templateSelect.value || "")];
            if (!selected) {
                return;
            }

            messageInput.value = selected.message || "";
            if (languageSelect && selected.language) {
                languageSelect.value = selected.language;
            }
            messageInput.dispatchEvent(new Event("input", { bubbles: true }));
        });
    }

    function initializeAudiencePanels() {
        const audienceSelect = document.getElementById("id_audience");
        const panels = Array.from(document.querySelectorAll("[data-audience-panel]"));
        if (!audienceSelect || !panels.length) {
            return;
        }

        const updatePanels = () => {
            const selected = audienceSelect.value;
            panels.forEach((panel) => {
                const panelName = panel.getAttribute("data-audience-panel");
                panel.hidden = panelName !== selected;
            });
        };

        audienceSelect.addEventListener("change", updatePanels);
        updatePanels();
    }

    function initializeConfirmForms() {
        document.querySelectorAll("form[data-confirm]").forEach((form) => {
            form.addEventListener("submit", (event) => {
                const message = form.getAttribute("data-confirm") || "Continue?";
                if (!window.confirm(message)) {
                    event.preventDefault();
                }
            });
        });
    }

    function initializeSenderNormalization() {
        const senderInput = document.getElementById("id_name");
        if (!senderInput || !window.location.pathname.includes("/sms/senders/")) {
            return;
        }

        senderInput.addEventListener("input", () => {
            senderInput.value = senderInput.value
                .toUpperCase()
                .replace(/[^A-Z0-9]/g, "")
                .slice(0, 11);
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        initializeMessagePreview();
        initializeTemplateSelection();
        initializeAudiencePanels();
        initializeConfirmForms();
        initializeSenderNormalization();
    });
})();
