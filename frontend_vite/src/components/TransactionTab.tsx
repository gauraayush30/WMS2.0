import React from "react";

function TransactionTab({
  transactionForm,
  onFormChange,
  onSubmit,
  transactionLoading,
  transactionMessage,
  transactionError,
  skuInfo,
}) {
  return (
    <div className="transaction-container">
      <div className="transaction-form-box">
        <h2>Record Sales / Purchase Transaction</h2>
        <p className="form-subtitle">
          Update inventory for {transactionForm.sku_id || "selected SKU"}
        </p>

        <form onSubmit={onSubmit} className="transaction-form">
          <div className="form-group">
            <label htmlFor="transaction-date">Transaction Date</label>
            <input
              id="transaction-date"
              type="date"
              value={transactionForm.transaction_date}
              onChange={(e) =>
                onFormChange({ ...transactionForm, transaction_date: e.target.value })
              }
              disabled={transactionLoading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="sales-qty">Sales Quantity</label>
            <input
              id="sales-qty"
              type="number"
              min="0"
              value={transactionForm.sales_qty}
              onChange={(e) =>
                onFormChange({
                  ...transactionForm,
                  sales_qty: Math.max(0, parseInt(e.target.value) || 0),
                })
              }
              disabled={transactionLoading}
              placeholder="Units sold"
            />
          </div>

          <div className="form-group">
            <label htmlFor="purchase-qty">Purchase Quantity</label>
            <input
              id="purchase-qty"
              type="number"
              min="0"
              value={transactionForm.purchase_qty}
              onChange={(e) =>
                onFormChange({
                  ...transactionForm,
                  purchase_qty: Math.max(0, parseInt(e.target.value) || 0),
                })
              }
              disabled={transactionLoading}
              placeholder="Units purchased"
            />
          </div>

          {transactionError && (
            <div className="alert alert-error">{transactionError}</div>
          )}
          {transactionMessage && (
            <div className="alert alert-success">{transactionMessage}</div>
          )}

          <button
            type="submit"
            className="btn-submit"
            disabled={transactionLoading}
          >
            {transactionLoading ? "Recording..." : "Record Transaction"}
          </button>
        </form>

        {skuInfo && (
          <div className="transaction-stats">
            <div className="stat-item">
              <span className="stat-label">Current Stock</span>
              <span className="stat-value">{skuInfo.current_stock} units</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">SKU Name</span>
              <span className="stat-value">{skuInfo.sku_name}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Total Records</span>
              <span className="stat-value">{skuInfo.total_records}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default TransactionTab;
