import allure
from tests.ui.pages.base_page import BasePage
from core.log_factory import log


class DashboardPage(BasePage):
    """
    SauceDemo 商品列表页（登录后主页）
    """

    TITLE           = ".title"
    PRODUCT_LIST    = ".inventory_list"
    PRODUCT_ITEM    = ".inventory_item"
    PRODUCT_NAME    = ".inventory_item_name"
    ADD_TO_CART_BTN = "[data-test^='add-to-cart']"
    CART_BADGE      = ".shopping_cart_badge"
    SORT_SELECT     = "[data-test='product_sort_container']"
    MENU_BUTTON     = "#react-burger-menu-btn"
    LOGOUT_LINK     = "#logout_sidebar_link"

    @allure.step("验证进入商品列表页")
    def verify_on_page(self) -> "DashboardPage":
        self.assert_url_contains("inventory.html")
        self.assert_visible(self.PRODUCT_LIST)
        log.info("✓ 已进入商品列表页")
        return self

    def get_product_count(self) -> int:
        return self.count_elements(self.PRODUCT_ITEM)

    def get_product_names(self) -> list[str]:
        items = self.page.locator(self.PRODUCT_NAME).all()
        return [item.inner_text() for item in items]

    @allure.step("添加第一件商品到购物车")
    def add_first_item_to_cart(self) -> "DashboardPage":
        self.page.locator(self.ADD_TO_CART_BTN).first.click()
        return self

    def get_cart_count(self) -> int:
        if self.is_element_visible(self.CART_BADGE):
            return int(self.get_text(self.CART_BADGE))
        return 0

    @allure.step("按条件排序: {sort_type}")
    def sort_products(self, sort_type: str) -> "DashboardPage":
        """sort_type: az | za | lohi | hilo"""
        self.select_option(self.SORT_SELECT, sort_type)
        return self

    @allure.step("退出登录")
    def logout(self) -> None:
        self.click(self.MENU_BUTTON)
        self.assert_visible(self.LOGOUT_LINK)
        self.click(self.LOGOUT_LINK)
        self.assert_url_contains("www.saucedemo.com")
        log.info("✓ 已退出登录")