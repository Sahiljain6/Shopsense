FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

COPY payments/parbad-service/ShopSense.ParbadService.csproj ./payments/parbad-service/
RUN dotnet restore ./payments/parbad-service/ShopSense.ParbadService.csproj

COPY payments/parbad-service/ ./payments/parbad-service/
RUN dotnet publish ./payments/parbad-service/ShopSense.ParbadService.csproj \
    --configuration Release \
    --output /app/publish \
    --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:9.0
WORKDIR /app
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080
COPY --from=build /app/publish .
ENTRYPOINT ["dotnet", "ShopSense.ParbadService.dll"]
