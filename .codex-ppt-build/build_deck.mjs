import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";
import sharp from "sharp";

const BUILD = "C:/dev/cat-game-backend/.codex-ppt-build";
const SRC = path.join(BUILD, "source-render");
const OUT = path.join(BUILD, "candidate.pptx");

const W = 1280;
const H = 720;
const FONT = "Noto Sans KR";
const C = {
  bg: "#FFF9EF",
  paper: "#FFFDF7",
  paper2: "#FFF2E3",
  ink: "#3B281E",
  muted: "#6E584C",
  orange: "#F28A45",
  orange2: "#FFD2AE",
  orange3: "#FFF0E4",
  green: "#80985E",
  green2: "#E9F0D9",
  brown: "#9B6846",
  line: "#EAA16C",
  red: "#D96552",
  blue: "#7397B5",
  gray: "#ECE6DC",
  white: "#FFFFFF",
};

const deck = Presentation.create({ slideSize: { width: W, height: H } });
const imageCache = new Map();
const footerBytes = new Uint8Array(
  await sharp(path.join(SRC, "slide-1.png"))
    .extract({ left: 0, top: 620, width: W, height: 100 })
    .png()
    .toBuffer(),
);

async function imageBytes(n) {
  if (!imageCache.has(n)) {
    imageCache.set(n, new Uint8Array(await fs.readFile(path.join(SRC, `slide-${n}.png`))));
  }
  return imageCache.get(n);
}

function box(slide, x, y, w, h, fill = C.paper, line = C.line, radius = 18, shadow = null) {
  return slide.shapes.add({
    geometry: "roundRect",
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill: line, width: 2 },
    borderRadius: radius,
    ...(shadow ? { shadow } : {}),
  });
}

function text(slide, value, x, y, w, h, size = 22, options = {}) {
  const t = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  t.text = value;
  t.text.style = {
    typeface: options.typeface ?? FONT,
    fontSize: size,
    bold: options.bold ?? false,
    color: options.color ?? C.ink,
    alignment: options.align ?? "left",
    verticalAlignment: options.valign ?? "top",
    autoFit: options.autoFit ?? "shrinkText",
    wrap: "square",
    insets: options.insets ?? { left: 2, right: 2, top: 2, bottom: 2 },
  };
  return t;
}

function pill(slide, label, x, y, w, fill = C.orange, color = C.white, size = 18) {
  const p = box(slide, x, y, w, 38, fill, fill, 20);
  p.text = label;
  p.text.style = {
    typeface: FONT,
    fontSize: size,
    bold: true,
    color,
    alignment: "center",
    verticalAlignment: "middle",
    autoFit: "shrinkText",
    insets: { left: 8, right: 8, top: 2, bottom: 2 },
  };
  return p;
}

async function addCrop(slide, n, srcRect, frame, alt, radius = 18) {
  const [sx, sy, sw, sh] = srcRect;
  return slide.images.add({
    blob: await imageBytes(n),
    contentType: "image/png",
    alt,
    fit: "cover",
    position: { left: frame[0], top: frame[1], width: frame[2], height: frame[3] },
    crop: {
      left: sx / W,
      top: sy / H,
      right: 1 - (sx + sw) / W,
      bottom: 1 - (sy + sh) / H,
    },
    geometry: "roundRect",
    borderRadius: radius,
  });
}

async function themedSlide(title, subtitle = "") {
  const slide = deck.slides.add();
  slide.background.fill = C.bg;
  // 기존 자료의 산뜻한 언덕 하단부를 배경 장식으로 재사용한다.
  slide.images.add({
    blob: footerBytes,
    contentType: "image/png",
    alt: "기존 발표 자료의 고양이와 언덕 장식",
    fit: "cover",
    position: { left: 0, top: 620, width: W, height: 100 },
  });
  text(slide, "🐾", 56, 36, 50, 50, 30, { color: C.orange, bold: true, valign: "middle" });
  text(slide, title, 106, 30, 940, 60, 38, { bold: true, valign: "middle" });
  if (subtitle) text(slide, subtitle, 108, 86, 1010, 36, 18, { color: C.muted });
  text(slide, "고양이와 함께 배우는 즐거운 하루", 1005, 38, 220, 50, 15, { color: C.brown, align: "right", valign: "middle" });
  slide.shapes.add({
    geometry: "line",
    position: { left: 108, top: 116, width: 250, height: 0 },
    fill: "none",
    line: { style: "solid", fill: C.orange, width: 4 },
  });
  return slide;
}

function notes(slide, body, sources = []) {
  const src = sources.length ? `\n\nSources:\n${sources.map((s) => `- ${s}`).join("\n")}` : "";
  slide.speakerNotes.textFrame.setText(`${body}${src}`);
  slide.speakerNotes.setVisible(true);
}

function flowNode(slide, label, detail, x, y, w, fill = C.paper) {
  const n = box(slide, x, y, w, 94, fill, C.line, 18, "shadow-sm");
  text(slide, label, x + 16, y + 14, w - 32, 30, 20, { bold: true, align: "center" });
  text(slide, detail, x + 14, y + 51, w - 28, 30, 14, { color: C.muted, align: "center" });
  return n;
}

function arrow(slide, x, y, w = 46) {
  text(slide, "→", x, y, w, 46, 32, { color: C.orange, bold: true, align: "center", valign: "middle" });
}

function bulletList(slide, items, x, y, w, size = 18, gap = 42, color = C.ink) {
  items.forEach((item, i) => {
    text(slide, "●", x, y + i * gap + 2, 24, 24, 11, { color: i % 2 ? C.green : C.orange, valign: "middle" });
    text(slide, item, x + 28, y + i * gap, w - 28, gap - 2, size, { color, valign: "middle" });
  });
}

// 1. Cover
{
  const slide = await themedSlide("고양이와 함께하는 프로그래밍 학습 게임", "KANT-2 · 프런트엔드 × 백엔드 통합 발표");
  box(slide, 60, 156, 510, 370, C.paper, C.line, 28, "shadow-md");
  pill(slide, "LEARN · REWARD · DECORATE", 92, 190, 340, C.orange, C.white, 16);
  text(slide, "공부한 만큼\n내 공간과 고양이가 자랍니다", 88, 248, 430, 112, 34, { bold: true });
  text(slide, "학습 → 보상 → 수집 → 교감으로 이어지는\n동기부여형 코딩 학습 경험", 90, 382, 430, 76, 20, { color: C.muted });
  text(slide, "2026. 09", 92, 476, 220, 30, 16, { color: C.brown, bold: true });
  await addCrop(slide, 1, [488, 170, 754, 452], [610, 148, 610, 390], "고양이 게임 홈 화면", 26);
  notes(slide, "첫 문장은 기능 나열보다 게임의 학습 루프를 설명합니다. 발표 전체는 사용자 경험 → 구현 구조 → 안정성 순서입니다.", ["기존 48장 통합 발표 자료", "Notion: cat-game 오류 수정"]);
}

// 2. Home screen (source)
{
  const slide = deck.slides.add();
  slide.images.add({ blob: await imageBytes(1), contentType: "image/png", alt: "홈 화면 소개", fit: "cover", position: { left: 0, top: 0, width: W, height: H } });
  notes(slide, "홈 화면은 현재 상태, 대표 고양이와 핵심 기능으로 들어가는 허브입니다. 실제 프로필 버튼의 고양이는 사용자가 선택한 대표 고양이입니다.", ["C:/dev/cat-game/src/game/scenes/HomeScene.ts"]);
}

// 3. Learning screen (source)
{
  const slide = deck.slides.add();
  slide.images.add({ blob: await imageBytes(5), contentType: "image/png", alt: "학습 화면 소개", fit: "cover", position: { left: 0, top: 0, width: W, height: H } });
  notes(slide, "Python과 SQL 과목을 화면에서 바로 전환합니다. 숙련도와 추천 과제를 한 화면에 배치해 다음 행동이 끊기지 않도록 했습니다.", ["C:/dev/cat-game/docs/ARCHITECTURE.md", "C:/dev/cat-game-backend/docs/features/part2-learning-system.md"]);
}

// 4. Answer / grading (source)
{
  const slide = deck.slides.add();
  slide.images.add({ blob: await imageBytes(9), contentType: "image/png", alt: "정답 입력 화면 소개", fit: "cover", position: { left: 0, top: 0, width: W, height: H } });
  notes(slide, "코드 작성은 CodeMirror DOM 오버레이를 사용하고, 나머지 화면은 PixiJS Canvas에 유지했습니다. 제출 뒤에는 공개 가능한 판정 결과만 사용자에게 보여 줍니다.", ["C:/dev/cat-game/docs/CODE_GUIDE.md", "C:/dev/cat-game-backend/docs/features/part2-learning-system.md"]);
}

// 5. Daily + attendance
{
  const slide = await themedSlide("매일 돌아오게 만드는 루프", "학습 기록이 퀘스트와 출석 보상으로 자연스럽게 이어집니다.");
  await addCrop(slide, 13, [482, 170, 758, 452], [64, 152, 548, 330], "데일리 퀘스트 화면", 22);
  await addCrop(slide, 41, [492, 170, 748, 452], [668, 152, 548, 330], "출석 현황 화면", 22);
  pill(slide, "1  문제 완료", 128, 512, 210, C.orange);
  arrow(slide, 353, 510, 52);
  pill(slide, "2  퀘스트 보상", 414, 512, 220, C.green);
  arrow(slide, 646, 510, 52);
  pill(slide, "3  출석 스트릭", 710, 512, 220, C.orange);
  arrow(slide, 941, 510, 52);
  pill(slide, "4  다음 학습", 1002, 512, 190, C.green);
  text(slide, "현재 퀘스트 보상은 코인만 제공", 206, 566, 870, 28, 18, { color: C.orange, bold: true, align: "center" });
  text(slide, "오늘 문제를 풀지 않았다면 연속 학습 문구를 표시하지 않습니다.", 206, 592, 870, 26, 16, { color: C.muted, align: "center" });
  notes(slide, "데일리 퀘스트는 오늘 실제 완료 기록을 기준으로 활성화됩니다. 출석은 서버 날짜와 원장을 기준으로 중복 수령을 막고, 스트릭은 전날 출석이 있어야 이어집니다.", ["C:/dev/cat-game/docs/CODE_GUIDE.md", "C:/dev/cat-game-backend/docs/architecture/current-erd.md"]);
}

// 6. Economy and housing
{
  const slide = await themedSlide("보상이 공간으로 바뀌는 경제·하우징", "코인 하나로 구매하고, 보유 자산을 배치해 나만의 방을 완성합니다.");
  const cards = [
    { n: 17, title: "상점", sub: "서버 가격·잔액 검증", x: 56 },
    { n: 21, title: "보유", sub: "통합 assets 조회", x: 438 },
    { n: 25, title: "배치", sub: "소유권·좌표 검증", x: 820 },
  ];
  for (const c of cards) {
    box(slide, c.x, 150, 350, 386, C.paper, C.line, 22, "shadow-sm");
    await addCrop(slide, c.n, [488, 170, 752, 450], [c.x + 16, 168, 318, 220], `${c.title} 화면`, 14);
    text(slide, c.title, c.x + 24, 410, 302, 34, 25, { bold: true, align: "center" });
    text(slide, c.sub, c.x + 24, 452, 302, 32, 17, { color: C.muted, align: "center" });
    pill(slide, c.title === "보유" ? "Asset" : c.title === "상점" ? "Purchase" : "Placement", c.x + 100, 493, 150, c.title === "보유" ? C.green : C.orange, C.white, 15);
  }
  text(slide, "구매 · 자산 지급 · 잔액 변경은 한 트랜잭션으로 처리", 315, 570, 650, 32, 20, { bold: true, color: C.brown, align: "center" });
  notes(slide, "프런트는 구매 성공 여부를 자체 판정하지 않고 GameClient의 명령 결과와 서버 스냅샷만 반영합니다. 백엔드는 잔액 차감과 자산 지급을 원자적으로 처리합니다.", ["C:/dev/cat-game/docs/ARCHITECTURE.md", "C:/dev/cat-game-backend/docs/architecture/part3-integration-contract.md"]);
}

// 7. Gacha and catalog
{
  const slide = await themedSlide("뽑기의 재미와 도감의 목표", "중복 보상과 전체 카탈로그를 서버 데이터로 일관되게 관리합니다.");
  box(slide, 56, 150, 560, 390, C.paper, C.line, 24, "shadow-sm");
  box(slide, 664, 150, 560, 390, C.paper, C.line, 24, "shadow-sm");
  await addCrop(slide, 29, [490, 170, 750, 450], [76, 170, 520, 276], "고양이 뽑기 화면", 16);
  await addCrop(slide, 33, [490, 170, 750, 450], [684, 170, 520, 276], "고양이 도감 화면", 16);
  text(slide, "GACHA", 90, 470, 170, 34, 24, { bold: true, color: C.orange });
  text(slide, "request_id 멱등성 · 중복 고양이 보상", 218, 470, 360, 34, 17, { color: C.muted, valign: "middle" });
  text(slide, "CATALOG", 698, 470, 170, 34, 24, { bold: true, color: C.green });
  text(slide, "미보유 포함 전체 종류 · 보유 상태 표시", 844, 470, 340, 34, 17, { color: C.muted, valign: "middle" });
  pill(slide, "뽑기 결과 → assets 반영 → 도감 즉시 갱신", 323, 564, 634, C.brown, C.white, 18);
  notes(slide, "고양이 종류는 코드의 카탈로그 키와 DB 카탈로그 행을 기준으로 합니다. 뽑기 결과는 실행 원장과 assets를 같은 트랜잭션에서 갱신하고 도감은 전체 카탈로그를 조회합니다.", ["C:/dev/cat-game-backend/docs/architecture/current-erd.md", "C:/dev/cat-game-backend/docs/architecture/part3-integration-contract.md"]);
}

// 8. Cat conversation (source)
{
  const slide = deck.slides.add();
  slide.images.add({ blob: await imageBytes(37), contentType: "image/png", alt: "고양이 대화 화면 소개", fit: "cover", position: { left: 0, top: 0, width: W, height: H } });
  notes(slide, "대화는 고양이별 페르소나를 사용하고 사용자 원문은 저장하지 않습니다. 허용된 대화에서 서버가 만든 요약만 고양이 자산별 기억으로 누적하며, 현재 대화창의 ‘기억 초기화’로 해당 고양이의 기억만 삭제할 수 있습니다.", ["C:/dev/cat-game/docs/CODE_GUIDE.md", "C:/dev/cat-game-backend/docs/architecture/part3-integration-contract.md"]);
}

// 9. Profile flow (source)
{
  const slide = deck.slides.add();
  slide.images.add({ blob: await imageBytes(48), contentType: "image/png", alt: "프로필 화면 내부 동작 구조", fit: "cover", position: { left: 0, top: 0, width: W, height: H } });
  notes(slide, "학생관리시스템의 프로필 경로는 게임 백엔드가 프록시해 같은 출처에서 제공합니다. 연결되면 사용자 사진과 연동 완료, 실패하거나 이미지가 없으면 포근이와 연동 미완료를 보여 줍니다. 로그아웃은 서버 세션을 폐기합니다.", ["C:/dev/cat-game/src/services/BackendApiClient.ts", "C:/dev/cat-game/src/game/presentation/profileImage.ts", "Notion: cat-game 오류 수정"]);
}

// 10. Frontend architecture
{
  const slide = await themedSlide("프런트엔드: 화면과 규칙의 경계", "PixiJS 장면은 네트워크·저장소 구현을 모르고 GameClient 계약만 사용합니다.");
  const a = flowNode(slide, "PixiJS Scene", "화면·입력·애니메이션", 54, 166, 246, C.orange3);
  const b = flowNode(slide, "GameClient", "UI가 의존하는 단일 계약", 354, 166, 246, C.green2);
  const c = flowNode(slide, "BackendLearning\nGameClient", "서버 상태를 게임 상태로 변환", 654, 166, 246, C.orange3);
  const d = flowNode(slide, "BackendApiClient", "HTTP·JSON·Cookie·CSRF", 954, 166, 246, C.green2);
  [304, 604, 904].forEach((x) => arrow(slide, x, 190, 46));
  box(slide, 72, 316, 536, 216, C.paper, C.line, 22);
  pill(slide, "화면 계층", 94, 338, 150, C.orange);
  bulletList(slide, ["문구는 ko.json의 MessageId로 관리", "CodeMirror·IME 입력은 브리지로 격리", "실패를 임의의 로컬 성공으로 대체하지 않음"], 96, 394, 486, 17, 40);
  box(slide, 672, 316, 536, 216, C.paper, C.line, 22);
  pill(slide, "서버 상태 보호", 694, 338, 170, C.green);
  text(slide, "stateVersion", 706, 402, 210, 40, 30, { bold: true, color: C.green });
  text(slide, "현재 버전보다 작은 늦은 응답은 적용하지 않아\n동시 명령·재동기화의 화면 되돌림을 방지", 706, 450, 462, 58, 17, { color: C.muted });
  notes(slide, "프런트 아키텍처의 핵심은 화면과 구현을 분리한 GameClient입니다. 원격 모드에서는 모든 권위 상태를 서버 스냅샷으로 받아오고 stateVersion으로 응답 순서 역전을 방어합니다.", ["C:/dev/cat-game/docs/ARCHITECTURE.md", "C:/dev/cat-game/src/services/BackendLearningGameClient.ts"]);
}

// 11. Backend architecture
{
  const slide = await themedSlide("백엔드: 기능 중심 모듈형 모놀리스", "하나의 배포 단위 안에서 기능 경계와 트랜잭션 책임을 명확히 나눴습니다.");
  const nodes = [
    ["FastAPI Router", "HTTP · 인증 · DTO", 70, C.orange3],
    ["Service / UoW", "업무 규칙 · 트랜잭션", 350, C.green2],
    ["Repository", "조회 · 저장 · 행 잠금", 630, C.orange3],
    ["PostgreSQL", "22개 업무 테이블", 910, C.green2],
  ];
  nodes.map(([l, d, x, f]) => flowNode(slide, l, d, x, 168, 230, f));
  [302, 582, 862].forEach((x) => arrow(slide, x, 190, 42));
  const modules = ["identity", "learning", "grading", "daily", "shop", "gacha", "housing", "cats", "battle"];
  text(slide, "기능 모듈", 78, 322, 160, 34, 22, { bold: true });
  modules.forEach((m, i) => pill(slide, m, 76 + (i % 3) * 274, 368 + Math.floor(i / 3) * 58, 226, i % 2 ? C.green : C.orange, C.white, 16));
  box(slide, 936, 394, 242, 126, C.paper2, C.line, 18);
  text(slide, "내부 FK", 964, 410, 186, 30, 20, { bold: true, align: "center" });
  text(slide, "INTEGER", 964, 454, 186, 36, 25, { color: C.brown, bold: true, align: "center" });
  text(slide, "Repository는 commit하지 않고 서비스가 한 번만 커밋", 267, 556, 744, 34, 20, { color: C.brown, bold: true, align: "center" });
  notes(slide, "백엔드는 기능 중심 모듈형 모놀리스입니다. Repository는 조회·저장·잠금만 하고, 업무 서비스와 Unit of Work가 트랜잭션의 시작과 종료를 소유합니다.", ["C:/dev/cat-game-backend/docs/architecture/overview.md", "C:/dev/cat-game-backend/docs/architecture/current-erd.md", "C:/dev/cat-game-backend/docs/architecture/part3-integration-contract.md"]);
}

// 12. UUID conversion
{
  const slide = await themedSlide("API 경계: 내부 ID를 UUID로 변환", "DB 성능과 외부 안전성을 동시에 얻기 위해 식별자를 이중화했습니다.");
  box(slide, 60, 154, 352, 354, C.paper, C.line, 24, "shadow-sm");
  pill(slide, "DATABASE", 88, 180, 160, C.brown);
  text(slide, "id", 88, 246, 98, 34, 18, { color: C.muted });
  text(slide, "42", 230, 240, 130, 42, 30, { bold: true });
  text(slide, "cat_id", 88, 304, 118, 34, 18, { color: C.muted });
  text(slide, "7", 230, 298, 130, 42, 30, { bold: true });
  text(slide, "관계·잠금·조인은\nINTEGER PK/FK 사용", 88, 376, 270, 74, 21, { bold: true, color: C.brown });
  box(slide, 464, 216, 340, 224, C.orange3, C.orange, 30);
  text(slide, "명시적 DTO 변환", 504, 244, 260, 40, 26, { bold: true, align: "center" });
  text(slide, "cat.id → cat_public_id\nasset.id → cat_asset_public_id", 500, 308, 270, 72, 20, { align: "center", color: C.muted });
  text(slide, "→", 810, 293, 60, 70, 46, { bold: true, color: C.orange, align: "center", valign: "middle" });
  box(slide, 874, 154, 346, 354, C.paper, C.line, 24, "shadow-sm");
  pill(slide, "PUBLIC API", 902, 180, 176, C.green);
  text(slide, "public_id", 904, 246, 120, 34, 18, { color: C.muted });
  text(slide, "a17169ab-…", 904, 282, 270, 38, 24, { bold: true, color: C.green });
  text(slide, "cat_public_id", 904, 342, 160, 34, 18, { color: C.muted });
  text(slide, "fb8821d9-…", 904, 378, 270, 38, 24, { bold: true, color: C.green });
  text(slide, "내부 INTEGER id는\n요청·응답에 노출하지 않음", 904, 432, 270, 62, 19, { bold: true });
  pill(slide, "추측 가능한 순번 노출 방지 · 테이블 구조 변경 영향 축소 · 소유권 검사는 별도 수행", 146, 548, 988, C.orange, C.white, 17);
  notes(slide, "DB 안에서는 효율적인 정수 PK/FK를 사용하지만 API에는 UUID만 노출합니다. ORM 필드명과 응답 필드명이 다르므로 자동 변환에 기대지 않고 to_*_read 같은 명시적 DTO 변환 함수에서 관계를 공개 UUID로 치환합니다. UUID는 소유권 검사를 대신하지 않습니다.", ["C:/dev/cat-game-backend/docs/architecture/current-erd.md", "C:/dev/cat-game-backend/docs/architecture/part3-integration-contract.md", "C:/dev/cat-game-backend/app/schemas/task.py", "C:/dev/cat-game-backend/app/modules/cats/service.py"]);
}

// 13. Learning policy
{
  const slide = await themedSlide("학습 설계: 같은 문제를 다른 방식으로", "문제 수를 늘리는 것보다 난이도·표현·추천의 다양성을 함께 설계했습니다.");
  box(slide, 56, 154, 326, 360, C.paper, C.line, 22);
  text(slide, "300", 84, 184, 150, 66, 48, { bold: true, color: C.orange });
  text(slide, "총 학습 문제", 84, 250, 230, 32, 20, { bold: true });
  bulletList(slide, ["Python 150", "SQL 150", "난이도별 50문제"], 84, 312, 250, 20, 48);
  box(slide, 410, 154, 396, 360, C.paper, C.line, 22);
  text(slide, "객관식 표시 확률", 438, 184, 330, 36, 24, { bold: true });
  const rates = [["BRONZE", "50%", C.orange], ["SILVER", "20%", C.green], ["GOLD", "0%", C.brown]];
  rates.forEach(([name, value, fill], i) => {
    text(slide, name, 438, 252 + i * 74, 142, 32, 18, { bold: true });
    box(slide, 584, 250 + i * 74, 178, 30, C.gray, C.gray, 15);
    const width = name === "BRONZE" ? 89 : name === "SILVER" ? 36 : 4;
    box(slide, 584, 250 + i * 74, width, 30, fill, fill, 15);
    text(slide, value, 690, 246 + i * 74, 70, 34, 18, { bold: true, align: "right" });
  });
  box(slide, 834, 154, 390, 360, C.paper, C.line, 22);
  text(slide, "Presentation 세션", 862, 184, 330, 36, 24, { bold: true });
  bulletList(slide, ["유형·보기 순서를 서버가 결정", "A~D 정답 위치를 매번 섞음", "새로고침·재시도에는 고정", "추천 부족 시 범위를 단계적으로 확장"], 862, 246, 324, 17, 52);
  pill(slide, "한 논리 문제 → 직접 작성형 + 객관식 경험", 326, 552, 628, C.orange, C.white, 19);
  notes(slide, "Python과 SQL 각각 150문제입니다. BRONZE 50%, SILVER 20%, GOLD 0%로 객관식을 표시하고 나머지는 직접 작성형입니다. 표시 세션에서 보기와 정답 위치를 섞되 같은 세션에서는 새로고침해도 유지합니다.", ["C:/dev/cat-game-backend/docs/features/part2-learning-system.md", "C:/dev/cat-game-backend/app/modules/learning/presentation.py", "C:/dev/cat-game-backend/app/modules/learning/proficiency.py"]);
}

// 14. Grading pipeline
{
  const slide = await themedSlide("채점 파이프라인: API와 실행 환경 분리", "제출 코드는 API 프로세스가 직접 실행하지 않습니다.");
  const steps = [
    ["1  제출", "request_id 저장", 42, C.orange3],
    ["2  PENDING", "DB에 시도 생성", 286, C.green2],
    ["3  Worker 임대", "SKIP LOCKED", 530, C.orange3],
    ["4  격리 채점", "Python / SQL", 774, C.green2],
    ["5  결과·보상", "한 번만 커밋", 1018, C.orange3],
  ];
  steps.map(([l, d, x, f]) => flowNode(slide, l, d, x, 166, 214, f));
  [250, 494, 738, 982].forEach((x) => arrow(slide, x, 190, 34));
  box(slide, 76, 324, 542, 210, C.paper, C.line, 22);
  pill(slide, "격리", 100, 348, 116, C.orange);
  bulletList(slide, ["Python: 제한된 채점 컨테이너", "SQL: 운영 DB와 분리한 전용 PostgreSQL", "시간·출력·메모리 제한"], 104, 400, 478, 18, 40);
  box(slide, 660, 324, 542, 210, C.paper, C.line, 22);
  pill(slide, "공개 결과", 684, 348, 150, C.green);
  bulletList(slide, ["ACCEPTED / WRONG_ANSWER 등 판정", "passed / total만 응답", "테스트 케이스·표준 오류·제출 코드는 비공개"], 688, 400, 478, 18, 40);
  text(slide, "만료된 RUNNING 임대는 회수하고, lease token으로 늦은 워커 결과를 거부", 176, 566, 930, 30, 18, { color: C.brown, bold: true, align: "center" });
  notes(slide, "답안 제출 API는 PENDING 시도만 저장합니다. 워커가 FOR UPDATE SKIP LOCKED로 시도를 임대해 격리 실행하고, 임대 토큰으로 중복·지연 결과를 차단합니다. 결과와 최초 보상은 같은 트랜잭션에서 커밋합니다.", ["C:/dev/cat-game-backend/docs/architecture/overview.md", "C:/dev/cat-game-backend/docs/features/part2-learning-system.md", "C:/dev/cat-game-backend/app/modules/grading/service.py"]);
}

// 15. Idempotency / transaction
{
  const slide = await themedSlide("중복 요청에도 한 번만: 멱등성 트랜잭션", "네트워크 재시도와 더블 클릭이 잔액·자산을 두 번 바꾸지 않게 합니다.");
  box(slide, 56, 154, 500, 382, C.paper, C.line, 24);
  text(slide, "요청 지문", 86, 184, 200, 36, 25, { bold: true });
  text(slide, "request_id", 88, 248, 170, 32, 19, { color: C.muted });
  pill(slide, "UUID", 306, 244, 126, C.green);
  text(slide, "canonical JSON", 88, 312, 190, 32, 19, { color: C.muted });
  pill(slide, "정렬 + 공백 규칙", 306, 308, 174, C.orange);
  text(slide, "request_hash", 88, 376, 180, 32, 19, { color: C.muted });
  pill(slide, "SHA-256", 306, 372, 144, C.brown);
  text(slide, "같은 request_id + 같은 hash = 저장된 결과 재사용", 88, 452, 410, 44, 18, { bold: true, color: C.brown });
  box(slide, 602, 154, 622, 382, C.paper, C.line, 24);
  text(slide, "claim 결과", 632, 184, 200, 36, 25, { bold: true });
  const statuses = [
    ["ACQUIRED", "신규 요청 → 업무 처리", C.green],
    ["COMPLETED", "기존 성공 → 같은 결과 반환", C.orange],
    ["HASH_CONFLICT", "사용자·내용 다름 → 409", C.red],
  ];
  statuses.forEach(([s, d, f], i) => {
    pill(slide, s, 636, 246 + i * 76, 188, f, C.white, 15);
    text(slide, d, 848, 249 + i * 76, 322, 36, 18, { valign: "middle" });
  });
  text(slide, "잔액 차감 · 자산 지급 · 실행 결과 · stateVersion", 640, 470, 520, 30, 18, { color: C.muted, align: "center" });
  pill(slide, "ALL OR NOTHING — 한 번 커밋, 실패 시 전부 롤백", 238, 562, 804, C.brown, C.white, 19);
  notes(slide, "구매·뽑기·학습 제출은 request_id와 정규 JSON의 SHA-256 해시를 사용합니다. 동일한 요청 재전송은 저장된 결과를 반환하고, 같은 request_id에 다른 사용자나 내용이 오면 409로 거절합니다. 상태 변경 전체는 한 트랜잭션입니다.", ["C:/dev/cat-game-backend/app/core/request_hash.py", "C:/dev/cat-game-backend/docs/architecture/part3-integration-contract.md"]);
}

// 16. Runtime, auth, sync
{
  const slide = await themedSlide("통합 실행: 한 주소에서 세션과 상태 연결", "PWA·FastAPI·PostgreSQL·채점 워커를 역할별로 분리합니다.");
  const browser = flowNode(slide, "Browser / PWA", "PixiJS Canvas", 48, 162, 220, C.orange3);
  const nginx = flowNode(slide, "Nginx", "동일 출처 · CSP", 300, 162, 200, C.green2);
  const api = flowNode(slide, "FastAPI", "세션 · 게임 API", 532, 162, 220, C.orange3);
  const db = flowNode(slide, "PostgreSQL", "권위 상태 · 원장", 784, 162, 220, C.green2);
  const worker = flowNode(slide, "Grading Worker", "격리 실행 조율", 1036, 162, 200, C.orange3);
  [266, 498, 750, 1002].forEach((x) => arrow(slide, x, 186, 34));
  box(slide, 64, 318, 538, 220, C.paper, C.line, 22);
  pill(slide, "인증", 88, 342, 112, C.orange);
  bulletList(slide, ["HttpOnly 세션 쿠키", "상태 변경 요청은 CSRF 토큰 검증", "401이면 인증 화면으로 복귀"], 92, 400, 476, 18, 42);
  box(slide, 678, 318, 538, 220, C.paper, C.line, 22);
  pill(slide, "프로필 연동", 702, 342, 162, C.green);
  bulletList(slide, ["학생관리시스템 경로를 백엔드가 프록시", "연동 성공: 사용자 이미지", "미연동: 포근이 이미지 + 상태 문구"], 706, 400, 476, 18, 42);
  text(slide, "Docker Compose로 로컬 통합 실행 · 운영에서는 HTTPS와 동일 호스트 구성", 192, 570, 896, 30, 18, { color: C.brown, bold: true, align: "center" });
  notes(slide, "브라우저는 Nginx를 통해 프런트와 API를 같은 출처로 사용합니다. 세션 쿠키와 CSRF를 안전하게 적용하고, 게임 상태는 PostgreSQL이 권위를 갖습니다. 프로필 이미지는 백엔드 프록시를 거쳐 브라우저의 교차 출처 세션 문제를 제거합니다.", ["C:/dev/cat-game/docs/CODE_GUIDE.md", "C:/dev/cat-game/docs/DOCKER_INTEGRATION.md", "C:/dev/cat-game/src/services/BackendApiClient.ts", "Notion: cat-game 오류 수정"]);
}

// 17. Closing
{
  const slide = await themedSlide("결론: 학습 경험과 데이터 신뢰성을 함께 설계", "사용자에게는 즐거운 루프를, 팀에게는 확장 가능한 경계를 남겼습니다.");
  const stages = [
    ["학습", "추천·코드·객관식", 78, C.orange],
    ["보상", "퀘스트·출석·코인", 348, C.green],
    ["성장", "수집·상점·하우징", 618, C.orange],
    ["교감", "대화·고양이별 기억", 888, C.green],
  ];
  stages.forEach(([a, b, x, f], i) => {
    box(slide, x, 168, 230, 170, i % 2 ? C.green2 : C.orange3, f, 28, "shadow-sm");
    text(slide, a, x + 22, 200, 186, 46, 31, { bold: true, color: f, align: "center" });
    text(slide, b, x + 20, 262, 190, 42, 17, { color: C.muted, align: "center" });
    if (i < stages.length - 1) arrow(slide, x + 230, 225, 40);
  });
  box(slide, 118, 386, 1044, 148, C.paper, C.line, 24);
  const wins = [
    ["프런트", "GameClient 경계 + stateVersion"],
    ["백엔드", "UUID DTO + 원자적 트랜잭션"],
    ["운영", "세션·격리 채점 + 관측 가능성"],
  ];
  wins.forEach(([a, b], i) => {
    text(slide, a, 154 + i * 330, 414, 118, 30, 19, { bold: true, color: i === 1 ? C.orange : C.green });
    text(slide, b, 154 + i * 330, 456, 290, 40, 17, { color: C.muted });
  });
  pill(slide, "DEMO  홈 → 학습 → 정답 제출 → 보상 → 배치 → 고양이 대화", 236, 562, 808, C.brown, C.white, 18);
  notes(slide, "마지막에는 기능이 아니라 연결된 경험을 다시 강조합니다. 시연 순서는 홈, 학습, 제출, 보상, 배치, 고양이 대화이며 마지막에 프로필과 로그아웃을 짧게 확인합니다.", ["C:/dev/cat-game/docs/ARCHITECTURE.md", "C:/dev/cat-game-backend/docs/architecture/current-erd.md"]);
}

await fs.mkdir(BUILD, { recursive: true });
await (await PresentationFile.exportPptx(deck)).save(OUT);
console.log(`WROTE ${OUT}`);
console.log(`SLIDES ${deck.slides.items.length}`);
