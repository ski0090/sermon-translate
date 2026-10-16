// 창(modal): 화면 전체를 어둡게 덮고 가운데에 카드 하나를 띄운다. 내용은 slot으로 받는다
export default {
  template: `<div class="modal"><div class="card"><slot/></div></div>`,
};
