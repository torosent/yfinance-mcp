# yfinance MCP Server on Azure Functions

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server providing Yahoo Finance data, hosted on Azure Functions as a [self-hosted MCP server](https://learn.microsoft.com/en-us/azure/azure-functions/self-hosted-mcp-servers?pivots=programming-language-python).

Based on yfinance, adapted for Azure Functions using the custom handler pattern with streamable-http transport.

## Tools

| Tool | Description |
|------|-------------|
| `get_stock_info` | Get stock price, valuation, financials, and company info |
| `get_historical_data` | Get historical OHLCV price data with configurable period/interval |
| `get_dividends` | Get dividend payment history |
| `get_splits` | Get stock split history |
| `get_financials` | Get income statement, balance sheet, and cash flow (annual/quarterly) |
| `get_earnings` | Get earnings data from income statements |
| `get_news` | Get recent news articles for a stock |
| `get_recommendations` | Get analyst recommendations breakdown |
| `search_stocks` | Search for stocks by company name or ticker |
| `get_multiple_quotes` | Get quotes for multiple stocks at once |
| `get_option_chain` | Get options data with strikes, bid/ask, volume, implied volatility |
| `get_analyst_estimates` | Get EPS forecasts, revenue estimates, and growth projections |
| `get_analyst_ratings` | Get price targets and upgrade/downgrade history |
| `get_insider_holdings` | Get insider transactions, institutional and fund holders |
| `batch_download` | Download historical data for multiple tickers efficiently |
| `screen_stocks` | Screen stocks using predefined Yahoo Finance screeners |
| `get_esg_data` | Get ESG sustainability scores |
| `get_sec_filings` | Get SEC filings (10-K, 10-Q, 8-K) with links |
| `get_calendar` | Get upcoming earnings dates, ex-dividend, and estimates |

## Prerequisites

- [Python 3.11+](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/) (package manager)
- [Azure Functions Core Tools v4](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local) (for local dev and deployment)

## Local Development

```bash
# Install dependencies
uv sync

# Run with Azure Functions Core Tools
func start

# Or run the server directly (without Functions host)
uv run python server.py
```

The MCP server starts on `http://localhost:8000/mcp` using the streamable-http transport.

## Testing Locally

Send MCP requests to `http://localhost:8000/mcp`:

```bash
# Initialize the MCP session
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'

# List available tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# Call a tool (e.g., get stock info for AAPL)
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_stock_info","arguments":{"symbol":"AAPL"}}}'
```

Or connect any MCP client (VS Code Copilot, Claude Desktop, etc.) with:

```json
{
  "mcpServers": {
    "yfinance": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Deploy to Azure

The server is deployed to an **Azure Functions Flex Consumption plan** using the Azure CLI and Azure Functions Core Tools.

### 1. Create Azure Resources

```bash
az login

# Create a resource group
az group create --name <resource-group> --location <region>

# Create a storage account (required by Azure Functions)
az storage account create \
  --name <storage-account> \
  --resource-group <resource-group> \
  --location <region> \
  --sku Standard_LRS

# Create the Function App on Flex Consumption
az functionapp create \
  --name <function-app-name> \
  --resource-group <resource-group> \
  --storage-account <storage-account> \
  --flexconsumption-location <region> \
  --runtime python \
  --runtime-version 3.11
```

> **Region** must support Flex Consumption — see [supported regions](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to#view-currently-supported-regions).

### 2. Configure App Settings

```bash
az functionapp config appsettings set \
  --name <function-app-name> \
  --resource-group <resource-group> \
  --settings \
    "AzureWebJobsFeatureFlags=EnableMcpCustomHandlerPreview" \
    "PYTHONPATH=/home/site/wwwroot/.python_packages/lib/site-packages"
```

### 3. Build and Deploy

Azure Functions custom handlers require Python packages to be pre-built for the target platform (Linux x86_64, Python 3.11):

```bash
# Generate requirements.txt from pyproject.toml
uv pip compile pyproject.toml -o requirements.txt

# Install packages for the Azure Functions target platform
pip install -r requirements.txt \
  --target .python_packages/lib/site-packages \
  --platform manylinux2014_x86_64 \
  --python-version 3.11 \
  --only-binary=:all:

# Deploy (--no-build since packages are pre-built)
func azure functionapp publish <function-app-name> --python --no-build
```

After deployment, the server is live at `https://<function-app-name>.azurewebsites.net/mcp`.

## Authentication

Choose one of three authentication options depending on your security requirements.

### Option 1: No Authentication (Anonymous)

The server is open to the internet with no authentication. Anyone can connect.

This is the default configuration — `host.json` sets `DefaultAuthorizationLevel` to `anonymous`, and no App Service Authentication is configured.

No additional setup is required after deployment.

```json
{
  "mcpServers": {
    "yfinance": {
      "url": "https://<function-app-name>.azurewebsites.net/mcp"
    }
  }
}
```

### Option 2: Function Key Authentication

Azure Functions provides built-in key-based authentication. Clients must include a function key in each request.

#### Configure

1. Change `DefaultAuthorizationLevel` in `host.json` from `anonymous` to `function`:

   ```json
   {
     "customHandler": {
       "http": {
         "DefaultAuthorizationLevel": "function"
       }
     }
   }
   ```

2. Redeploy the function app.

3. Retrieve the default function key:

   ```bash
   az functionapp keys list \
     --name <function-app-name> \
     --resource-group <resource-group> \
     --query "functionKeys.default" -o tsv
   ```

#### Connect

Pass the key as a query parameter or header:

```json
{
  "mcpServers": {
    "yfinance": {
      "url": "https://<function-app-name>.azurewebsites.net/mcp?code=<function-key>"
    }
  }
}
```

Or use the `x-functions-key` header:

```bash
curl -X POST https://<function-app-name>.azurewebsites.net/mcp \
  -H "x-functions-key: <function-key>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

> **Note:** Function keys provide basic access control but are shared secrets. Rotate keys periodically via the Azure Portal or CLI. For production workloads with user-level access control, use Entra ID (Option 3).

### Option 3: Microsoft Entra ID (Recommended for Production)

[Built-in App Service Authentication](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-mcp) implements the [MCP authorization specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization). Clients receive a 401 challenge and must authenticate via OAuth before connecting.

#### 1. Configure an Identity Provider

1. In Azure Portal, open your function app → **Settings → Authentication**
2. [Add an identity provider](https://learn.microsoft.com/en-us/azure/app-service/overview-authentication-authorization#identity-providers) (e.g., Microsoft Entra ID)
3. The identity provider registration should be **unique** for this MCP server — don't reuse an existing registration from another app
4. Make note of the **scopes** defined in your registration (e.g., `api://<client-id>/user_impersonation`)
5. Under **App Service authentication settings**:

   | Setting | Value |
   |---------|-------|
   | Restrict access | Require authentication |
   | Unauthenticated requests | HTTP 401 Unauthorized |
   | Token store | ✅ Checked |

#### 2. Configure Protected Resource Metadata

MCP server authorization requires that the server host [protected resource metadata (PRM)](https://learn.microsoft.com/en-us/azure/app-service/overview-authentication-authorization#protected-resource-metadata-preview):

```bash
az functionapp config appsettings set \
  --name <function-app-name> \
  --resource-group <resource-group> \
  --settings "WEBSITE_AUTH_PRM_DEFAULT_WITH_SCOPES=api://<client-id>/user_impersonation"
```

#### 3. Preauthorize MCP Clients

Microsoft Entra ID does not support Dynamic Client Registration, so MCP clients must be preconfigured.

To preauthorize a client (e.g., VS Code):

1. On the Authentication page, click the Entra app name next to **Microsoft**
2. Go to **Manage → Expose an API**
3. Under **Authorized client applications**, click **+ Add a client application**
4. Enter the client ID (VS Code: `aebc6443-996d-45c2-90f0-388ff96faa56`)
5. Select the `user_impersonation` scope checkbox → **Add application**

> **Note:** Without preauthorization, users or an admin must consent to the MCP server registration. Some clients (e.g., GitHub Copilot in VS Code) don't surface interactive login prompts, so preauthorization is required. For dev/test, you can grant consent by navigating to `<your-app-url>/.auth/login/aad` in a browser.

#### Connect

```json
{
  "mcpServers": {
    "yfinance": {
      "url": "https://<function-app-name>.azurewebsites.net/mcp"
    }
  }
}
```

MCP clients that support the [MCP authorization specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization) (e.g., VS Code Copilot, Claude Desktop) will automatically handle the OAuth flow when connecting.

For full details, see [Configure built-in MCP server authorization](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-mcp) and the [Azure Functions MCP tutorial](https://learn.microsoft.com/en-us/azure/azure-functions/functions-mcp-tutorial).
