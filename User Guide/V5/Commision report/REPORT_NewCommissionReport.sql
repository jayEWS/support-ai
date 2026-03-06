CREATE PROCEDURE [dbo].[REPORT_NewCommissionReport]
	@FilterStartDate AS DATETIME,
	@FilterEndDate AS DATETIME,
	@FilterUserName AS NVARCHAR(500),
	@Generate AS INT = 0,
	@Month AS VARCHAR(20) = ''
AS
BEGIN
-- SET NOCOUNT ON added to prevent extra result sets from
-- interfering with SELECT statements.
SET NOCOUNT ON;
DECLARE @TempSales AS TABLE 
(
	Sales NVARCHAR(50)
	,ItemType NVARCHAR(50)
	,Category NVARCHAR(50)
	,ItemNo NVARCHAR(50)
	,ItemName NVARCHAR(50)
	,SalesTotalQuantity DECIMAL(20,5)
	,SalesTotalAmount MONEY
	,CommissionHdrID INT
	,SalesGroupID INT
);
DECLARE @TempResultP1 AS TABLE 
(
	ID INT IDENTITY(1,1) NOT NULL
	,Sales NVARCHAR(50)
	,CommissionHdrID INT
	,SchemeName NVARCHAR(50)
	,TotalAmount MONEY
	,TotalQuantity DECIMAL(18,2)
);
DECLARE @TempResultP2 AS TABLE 
(
	ID INT IDENTITY(1,1) NOT NULL
	,Sales NVARCHAR(50)
	,SchemeName NVARCHAR(50)
	,TotalAmount MONEY
	,TotalQuantity DECIMAL(18,2)
	,TotalCommission MONEY
);
DECLARE @TempDeductionAmount AS TABLE
(
	ID INT IDENTITY(1,1) NOT NULL
	,Sales NVARCHAR(50)
	,Amount MONEY
	,CommissionHdrID INT
);
DECLARE @CommissionHdrID INT;
DECLARE @SchemeName NVARCHAR(50);
DECLARE @IsProduct INT;
DECLARE @ProductWeight DECIMAL(5,2);
DECLARE @IsService INT;
DECLARE @ServiceWeight DECIMAL(5,2);
DECLARE @IsPointSold INT;
DECLARE @PointSoldWeight DECIMAL(5,2);
DECLARE @IsPackageSold INT;
DECLARE @PackageSoldWeight DECIMAL(5,2);
DECLARE @IsPointRedeem INT;
DECLARE @PointRedeemWeight DECIMAL(5,2);
DECLARE @IsPackageRedeem INT;
DECLARE @PackageRedeemWeight DECIMAL(5,2);
DECLARE @IsDeductionFor2ndSalesPerson INT;
DECLARE @DeductionBy VARCHAR(20);
DECLARE @DeductionValue DECIMAL(18,2);
DECLARE @SalesGroupID INT;
DECLARE @CommissionBy VARCHAR(20);
DECLARE @CommissionHdrID2 INT;
DECLARE @SchemeName2 NVARCHAR(50);
DECLARE @IsProduct2 INT;
DECLARE @ProductWeight2 DECIMAL(5,2);
DECLARE @IsService2 INT;
DECLARE @ServiceWeight2 DECIMAL(5,2);
DECLARE @IsPointSold2 INT;
DECLARE @PointSoldWeight2 DECIMAL(5,2);
DECLARE @IsPackageSold2 INT;
DECLARE @PackageSoldWeight2 DECIMAL(5,2);
DECLARE @IsPointRedeem2 INT;
DECLARE @PointRedeemWeight2 DECIMAL(5,2);
DECLARE @IsPackageRedeem2 INT;
DECLARE @PackageRedeemWeight2 DECIMAL(5,2);
DECLARE @IsDeductionFor2ndSalesPerson2 INT;
DECLARE @DeductionBy2 VARCHAR(20);
DECLARE @DeductionValue2 DECIMAL(18,2);
DECLARE @SalesGroupID2 INT;
DECLARE @CommissionBy2 VARCHAR(20);
DECLARE @CountFor INT;
DECLARE @CategoryName NVARCHAR(250);
DECLARE @ItemNo NVARCHAR(50);
DECLARE @UserFld1 NVARCHAR(50); -- sales
DECLARE @UserFld2 NVARCHAR(50); -- scheme
DECLARE @UserFld3 NVARCHAR(50); -- scheme (generate block)
DECLARE @UserFld4 NVARCHAR(50); -- commission type (generate block)
DECLARE @UserFloat1 MONEY; -- for amount
DECLARE @UserFloat2 DECIMAL(18,2); -- for quantity
DECLARE @UserFloat3 DECIMAL(18,2); -- for commission
DECLARE @UserFloat4 DECIMAL(18,2); -- for quantity (generate block)
DECLARE @UserFloat5 MONEY; -- for amount (generate block)
DECLARE @UserInt1 INT;
DECLARE @CommissionBasedOn VARCHAR(20);
DECLARE @From DECIMAL(18,2);
DECLARE @To DECIMAL(18,2);
DECLARE @Value DECIMAL(18,2);
DECLARE @Count_CFD INT;
-- load setting commission based on total/bracket
SELECT @CommissionBasedOn = AppSettingValue FROM AppSetting WHERE AppSettingKey = 'Commission_BasedOn';
IF OBJECT_ID('tempdb..#TempOrder') IS NOT NULL
  DROP TABLE #TempOrder
SELECT   UM.UserName Sales
		,UM.GroupName SalesGroupID
		,I.CategoryName
		,I.ItemNo
		,(CASE WHEN I.CategoryName = 'SYSTEM' THEN 'SYSTEM'  
               WHEN I.Userfld10 = 'D' THEN 'POINT_SOLD' 
               WHEN I.Userfld9 = 'D' AND ISNULL(OH.IsPointAllocated, 0) = 1 THEN 'POINT_REDEEM' 
               WHEN I.Userfld10 = 'T' AND ISNULL(OD.Userflag5,0) = 0 THEN 'PACKAGE_SOLD'  
               WHEN I.Userfld10 = 'T' AND ISNULL(OD.Userflag5,0) = 1 THEN 'PACKAGE_REDEEM'  
               WHEN I.IsCommission = 0 THEN 'NON_COMMISSION'  
               WHEN I.IsServiceItem = 1 AND I.IsInInventory = 0   THEN 'SERVICE'  
               WHEN I.IsServiceItem = 0 AND I.IsInInventory = 1   THEN 'PRODUCT'  
               WHEN I.IsServiceItem = 1 AND I.IsInInventory = 1   THEN 'PRODUCT'  
          END) AS ItemType
		,SUM(CASE
			WHEN I.Userfld10 = 'T' AND ISNULL(OD.Userflag5,0) = 1 THEN ISNULL(OD.Userfloat8, 0)
			ELSE OD.Amount END
		) Amount
		,SUM(OD.Quantity) Quantity
		,I.ItemName
		,UM2.UserName as Sales2ndPerson
		,UM2.GroupName as Sales2ndPersonGroupID
		,OH.OrderRefNo
INTO	#TempOrder
FROM	OrderHdr OH
		INNER JOIN SalesCommissionRecord SCR ON SCR.OrderHdrID = OH.OrderHdrID
		INNER JOIN OrderDet OD ON OD.OrderHdrID = OH.OrderHdrID
		INNER JOIN Item I ON I.ItemNo = OD.ItemNo
        INNER JOIN UserMst UM on UM.UserName = ISNULL(NULLIF(OD.UserFld1, ''), SCR.SalesPersonID)
        LEFT JOIN UserMst UM2 on UM2.UserName = ISNULL(OD.Userfld20, '')
WHERE	OH.IsVoided = 0
		AND OD.IsVoided =0 
		AND CAST(OH.OrderDate AS DATE) >= @FilterStartDate AND CAST(OH.OrderDate AS DATE) <= @FilterEndDate
		AND (
			(@FilterUserName = '' OR @FilterUserName = 'ALL' OR UM.UserName = @FilterUserName)
			OR (@FilterUserName = '' OR @FilterUserName = 'ALL' OR UM2.UserName = @FilterUserName)
		)
GROUP BY UM.UserName
		,UM.GroupName
		,I.CategoryName
		,I.ItemNo
		,I.ItemName
		,(CASE WHEN I.CategoryName = 'SYSTEM' THEN 'SYSTEM'  
               WHEN I.Userfld10 = 'D' THEN 'POINT_SOLD'  
               WHEN I.Userfld9 = 'D' AND ISNULL(OH.IsPointAllocated, 0) = 1 THEN 'POINT_REDEEM' 
               WHEN I.Userfld10 = 'T' AND ISNULL(OD.Userflag5,0) = 0 THEN 'PACKAGE_SOLD'  
               WHEN I.Userfld10 = 'T' AND ISNULL(OD.Userflag5,0) = 1 THEN 'PACKAGE_REDEEM'  
               WHEN I.IsCommission = 0 THEN 'NON_COMMISSION'  
               WHEN I.IsServiceItem = 1 AND I.IsInInventory = 0   THEN 'SERVICE'  
               WHEN I.IsServiceItem = 0 AND I.IsInInventory = 1   THEN 'PRODUCT'  
               WHEN I.IsServiceItem = 1 AND I.IsInInventory = 1   THEN 'PRODUCT'  
          END)
        ,UM2.UserName
        ,UM2.GroupName
        ,OH.OrderRefNo
ORDER BY UM.UserName, I.CategoryName, I.ItemNo
-- debug
--SELECT * FROM #TempOrder
--SELECT * FROM CommissionHdr
DECLARE db_cursor CURSOR LOCAL FOR
	SELECT 
		CommissionHdrID
		,SchemeName
		,IsProduct
		,ProductWeight
		,IsService
		,ServiceWeight
		,IsPointSold
		,PointSoldWeight
		,IsPackageSold
		,PackageSoldWeight
		,IsPointRedeem
		,PointRedeemWeight
		,IsPackageRedeem
		,PackageRedeemWeight
		,IsDeductionFor2ndSalesPerson
		,DeductionBy
		,DeductionValue
		,SalesGroupID
		,CommissionBy
	FROM CommissionHdr
OPEN db_cursor
FETCH NEXT FROM db_cursor INTO 
	@CommissionHdrID
	,@SchemeName
	,@IsProduct
	,@ProductWeight
	,@IsService
	,@ServiceWeight
	,@IsPointSold
	,@PointSoldWeight
	,@IsPackageSold
	,@PackageSoldWeight
	,@IsPointRedeem
	,@PointRedeemWeight
	,@IsPackageRedeem
	,@PackageRedeemWeight
	,@IsDeductionFor2ndSalesPerson
	,@DeductionBy
	,@DeductionValue
	,@SalesGroupID
	,@CommissionBy;
WHILE @@FETCH_STATUS = 0
BEGIN
	--SELECT @SchemeName as 'SchemeName', @IsDeductionFor2ndSalesPerson as 'IsDeductionFor2ndSalesPerson', @DeductionBy as 'DeductionBy', @SalesGroupID as 'SalesGroupID'
	
	IF @IsProduct = 1
	BEGIN
		INSERT INTO @TempSales
		SELECT 
			OH.Sales
			,OH.ItemType
			,OH.CategoryName
			,OH.ItemNo
			,OH.ItemName
			,OH.Quantity * @ProductWeight / 100
			,CASE 
				WHEN @IsDeductionFor2ndSalesPerson = 1 AND OH.Sales2ndPerson IS NOT NULL AND @DeductionBy = 'Percentage' THEN (OH.Amount * @ProductWeight / 100) * (100 - @DeductionValue) / 100
				ELSE (OH.Amount * @ProductWeight / 100)
			END as Amount
			,@CommissionHdrID
			,OH.SalesGroupID
		FROM #TempOrder OH
		WHERE OH.ItemType = 'PRODUCT'
		AND OH.SalesGroupID = @SalesGroupID
		
		IF @IsDeductionFor2ndSalesPerson = 1
		BEGIN
			IF @DeductionBy = 'Amount'
			BEGIN
				SELECT @Count_CFD = (SELECT COUNT(*) FROM CommissionDetFor WHERE CommissionHdrID = @CommissionHdrID)
				IF @Count_CFD > 0
				BEGIN
					INSERT INTO @TempDeductionAmount
					SELECT 
						OH.Sales, 
						-OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM CommissionDetFor CDF
					JOIN #TempOrder OH 
						ON (
							(OH.CategoryName = CDF.CategoryName AND OH.ItemNo = CDF.ItemNo) OR
							(OH.CategoryName = CDF.CategoryName AND ISNULL(OH.ItemNo, '') = '')
						)
					WHERE 
						CDF.CommissionHdrID = @CommissionHdrID
						AND OH.ItemType = 'PRODUCT' 
						AND OH.SalesGroupID = @SalesGroupID
						AND OH.Sales2ndPerson IS NOT NULL
						
					INSERT INTO @TempDeductionAmount
					SELECT 
						OH.Sales2ndPerson, 
						OH.Quantity * @DeductionValue
						,@CommissionHdrID 
					FROM CommissionDetFor CDF
					JOIN #TempOrder OH 
						ON (
							(OH.CategoryName = CDF.CategoryName AND OH.ItemNo = CDF.ItemNo) OR
							(OH.CategoryName = CDF.CategoryName AND ISNULL(OH.ItemNo, '') = '')
						)
					WHERE 
						CDF.CommissionHdrID = @CommissionHdrID
						AND OH.ItemType = 'PRODUCT'
						AND OH.SalesGroupID = @SalesGroupID
						AND OH.Sales2ndPerson IS NOT NULL
						--AND OH.Sales2ndPersonGroupID = @SalesGroupID
				END
				ELSE
				BEGIN
					INSERT INTO @TempDeductionAmount
					SELECT
						OH.Sales
						,-OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'PRODUCT' 
					AND OH.SalesGroupID = @SalesGroupID
					AND OH.Sales2ndPerson IS NOT NULL
					
					INSERT INTO @TempDeductionAmount
					SELECT
						OH.Sales2ndPerson
						,OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'PRODUCT' 
					AND OH.Sales2ndPerson IS NOT NULL
					AND OH.SalesGroupID = @SalesGroupID
					--AND OH.Sales2ndPersonGroupID = @SalesGroupID
				END
			END
			ELSE IF @CommissionBy = 'Percentage'
			BEGIN
				SELECT
					@UserInt1 = OH.Sales2ndPersonGroupID
				FROM #TempOrder OH
				WHERE OH.ItemType = 'PRODUCT'
				AND OH.Sales2ndPerson IS NOT NULL
				AND OH.SalesGroupID = @SalesGroupID
				
				DECLARE db_cursor5 CURSOR LOCAL FOR
					SELECT 
						CommissionHdrID
						,SchemeName
						,IsProduct
						,ProductWeight
						,IsService
						,ServiceWeight
						,IsPointSold
						,PointSoldWeight
						,IsPackageSold
						,PackageSoldWeight
						,IsPointRedeem
						,PointRedeemWeight
						,IsPackageRedeem
						,PackageRedeemWeight
						,IsDeductionFor2ndSalesPerson
						,DeductionBy
						,DeductionValue
						,SalesGroupID
						,CommissionBy
					FROM CommissionHdr
					WHERE
						SalesGroupID = @UserInt1
	
				OPEN db_cursor5
				FETCH NEXT FROM db_cursor5 INTO 
					@CommissionHdrID2
					,@SchemeName2
					,@IsProduct2
					,@ProductWeight2
					,@IsService2
					,@ServiceWeight2
					,@IsPointSold2
					,@PointSoldWeight2
					,@IsPackageSold2
					,@PackageSoldWeight2
					,@IsPointRedeem2
					,@PointRedeemWeight2
					,@IsPackageRedeem2
					,@PackageRedeemWeight2
					,@IsDeductionFor2ndSalesPerson2
					,@DeductionBy2
					,@DeductionValue2
					,@SalesGroupID2
					,@CommissionBy2;
	
				WHILE @@FETCH_STATUS = 0
				BEGIN
					INSERT INTO @TempSales
					SELECT 
						OH.Sales2ndPerson
						,OH.ItemType
						,OH.CategoryName
						,OH.ItemNo
						,OH.ItemName
						,OH.Quantity
						,(OH.Amount * @ProductWeight2 / 100) * @DeductionValue / 100 as Amount
						,@CommissionHdrID2
						,OH.Sales2ndPersonGroupID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'PRODUCT'
					AND OH.Sales2ndPerson IS NOT NULL
					AND OH.SalesGroupID = @SalesGroupID
					AND @CommissionBy = 'Percentage'
					
					FETCH NEXT FROM db_cursor5 INTO 
						@CommissionHdrID2
						,@SchemeName2
						,@IsProduct2
						,@ProductWeight2
						,@IsService2
						,@ServiceWeight2
						,@IsPointSold2
						,@PointSoldWeight2
						,@IsPackageSold2
						,@PackageSoldWeight2
						,@IsPointRedeem2
						,@PointRedeemWeight2
						,@IsPackageRedeem2
						,@PackageRedeemWeight2
						,@IsDeductionFor2ndSalesPerson2
						,@DeductionBy2
						,@DeductionValue2
						,@SalesGroupID2
						,@CommissionBy2;
				END
				
				CLOSE db_cursor5
				
				DEALLOCATE db_cursor5					
			END
		END
	END
	
	IF @IsService = 1
	BEGIN
		INSERT INTO @TempSales
		SELECT 
			OH.Sales
			,OH.ItemType
			,OH.CategoryName
			,OH.ItemNo
			,OH.ItemName
			,OH.Quantity * @ServiceWeight / 100
			,CASE 
				WHEN @IsDeductionFor2ndSalesPerson = 1 AND OH.Sales2ndPerson IS NOT NULL AND @DeductionBy = 'Percentage' THEN (OH.Amount * @ServiceWeight / 100) * (100 - @DeductionValue) / 100
				ELSE (OH.Amount * @ServiceWeight / 100)
			END as Amount
			,@CommissionHdrID
			,OH.SalesGroupID
		FROM #TempOrder OH
		WHERE OH.ItemType = 'SERVICE'
		AND OH.SalesGroupID = @SalesGroupID
		
		IF @IsDeductionFor2ndSalesPerson = 1
		BEGIN
			IF @DeductionBy = 'Amount'
			BEGIN
				SELECT @Count_CFD = (SELECT COUNT(*) FROM CommissionDetFor WHERE CommissionHdrID = @CommissionHdrID)
				IF @Count_CFD > 0
				BEGIN
					INSERT INTO @TempDeductionAmount
					SELECT 
						OH.Sales, 
						-OH.Quantity * @DeductionValue 
						,@CommissionHdrID
					FROM CommissionDetFor CDF
					JOIN #TempOrder OH 
						ON (
							(OH.CategoryName = CDF.CategoryName AND OH.ItemNo = CDF.ItemNo) OR
							(OH.CategoryName = CDF.CategoryName AND ISNULL(OH.ItemNo, '') = '')
						)
					WHERE 
						CDF.CommissionHdrID = @CommissionHdrID
						AND OH.ItemType = 'SERVICE'
						AND OH.SalesGroupID = @SalesGroupID
						AND OH.Sales2ndPerson IS NOT NULL
						
					INSERT INTO @TempDeductionAmount
					SELECT 
						OH.Sales2ndPerson, 
						OH.Quantity * @DeductionValue 
						,@CommissionHdrID
					FROM CommissionDetFor CDF
					JOIN #TempOrder OH 
						ON (
							(OH.CategoryName = CDF.CategoryName AND OH.ItemNo = CDF.ItemNo) OR
							(OH.CategoryName = CDF.CategoryName AND ISNULL(OH.ItemNo, '') = '')
						)
					WHERE 
						CDF.CommissionHdrID = @CommissionHdrID
						AND OH.ItemType = 'SERVICE'
						AND OH.SalesGroupID = @SalesGroupID
						AND OH.Sales2ndPerson IS NOT NULL
						--AND OH.Sales2ndPersonGroupID = @SalesGroupID
				END
				ELSE
				BEGIN
					INSERT INTO @TempDeductionAmount
					SELECT
						OH.Sales
						,-OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'SERVICE' 
					AND OH.SalesGroupID = @SalesGroupID
					AND OH.Sales2ndPerson IS NOT NULL
					
					INSERT INTO @TempDeductionAmount
					SELECT
						OH.Sales2ndPerson
						,OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'SERVICE' 
					AND OH.SalesGroupID = @SalesGroupID
					AND OH.Sales2ndPerson IS NOT NULL
					--AND OH.Sales2ndPersonGroupID = @SalesGroupID
				END				
			END
			ELSE
			BEGIN
				SELECT
					@UserInt1 = OH.Sales2ndPersonGroupID
				FROM #TempOrder OH
				WHERE OH.ItemType = 'SERVICE'
				AND OH.Sales2ndPerson IS NOT NULL
				AND OH.SalesGroupID = @SalesGroupID
				
				DECLARE db_cursor5 CURSOR LOCAL FOR
					SELECT 
						CommissionHdrID
						,SchemeName
						,IsProduct
						,ProductWeight
						,IsService
						,ServiceWeight
						,IsPointSold
						,PointSoldWeight
						,IsPackageSold
						,PackageSoldWeight
						,IsPointRedeem
						,PointRedeemWeight
						,IsPackageRedeem
						,PackageRedeemWeight
						,IsDeductionFor2ndSalesPerson
						,DeductionBy
						,DeductionValue
						,SalesGroupID
						,CommissionBy
					FROM CommissionHdr
					WHERE
						SalesGroupID = @UserInt1
	
				OPEN db_cursor5
				FETCH NEXT FROM db_cursor5 INTO 
					@CommissionHdrID2
					,@SchemeName2
					,@IsProduct2
					,@ProductWeight2
					,@IsService2
					,@ServiceWeight2
					,@IsPointSold2
					,@PointSoldWeight2
					,@IsPackageSold2
					,@PackageSoldWeight2
					,@IsPointRedeem2
					,@PointRedeemWeight2
					,@IsPackageRedeem2
					,@PackageRedeemWeight2
					,@IsDeductionFor2ndSalesPerson2
					,@DeductionBy2
					,@DeductionValue2
					,@SalesGroupID2
					,@CommissionBy2;
	
				WHILE @@FETCH_STATUS = 0
				BEGIN
					INSERT INTO @TempSales
					SELECT 
						OH.Sales2ndPerson
						,OH.ItemType
						,OH.CategoryName
						,OH.ItemNo
						,OH.ItemName
						,OH.Quantity
						,(OH.Amount * @ProductWeight2 / 100) * @DeductionValue / 100 as Amount
						,@CommissionHdrID2
						,OH.Sales2ndPersonGroupID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'SERVICE'
					AND OH.Sales2ndPerson IS NOT NULL
					AND OH.SalesGroupID = @SalesGroupID
					AND @CommissionBy = 'Percentage'
					
					FETCH NEXT FROM db_cursor5 INTO 
						@CommissionHdrID2
						,@SchemeName2
						,@IsProduct2
						,@ProductWeight2
						,@IsService2
						,@ServiceWeight2
						,@IsPointSold2
						,@PointSoldWeight2
						,@IsPackageSold2
						,@PackageSoldWeight2
						,@IsPointRedeem2
						,@PointRedeemWeight2
						,@IsPackageRedeem2
						,@PackageRedeemWeight2
						,@IsDeductionFor2ndSalesPerson2
						,@DeductionBy2
						,@DeductionValue2
						,@SalesGroupID2
						,@CommissionBy2;
				END
				
				CLOSE db_cursor5
				
				DEALLOCATE db_cursor5
			END
		END
	END
	
	IF @IsPointSold = 1
	BEGIN
		INSERT INTO @TempSales
		SELECT 
			OH.Sales
			,OH.ItemType
			,OH.CategoryName
			,OH.ItemNo
			,OH.ItemName
			,OH.Quantity * @PointSoldWeight / 100
			,CASE 
				WHEN @IsDeductionFor2ndSalesPerson = 1 AND OH.Sales2ndPerson IS NOT NULL AND @DeductionBy = 'Percentage' THEN (OH.Amount * @PointSoldWeight / 100) * (100 - @DeductionValue) / 100
				ELSE (OH.Amount * @PointSoldWeight / 100)
			END as Amount
			,@CommissionHdrID
			,OH.SalesGroupID
		FROM #TempOrder OH
		WHERE OH.ItemType = 'POINT_SOLD'
		AND OH.SalesGroupID = @SalesGroupID;
		
		IF @IsDeductionFor2ndSalesPerson = 1
		BEGIN
			IF @DeductionBy = 'Amount'
			BEGIN
				SELECT @Count_CFD = (SELECT COUNT(*) FROM CommissionDetFor WHERE CommissionHdrID = @CommissionHdrID)
				IF @Count_CFD > 0
				BEGIN
					INSERT INTO @TempDeductionAmount
					SELECT 
						OH.Sales, 
						-OH.Quantity * @DeductionValue 
						,@CommissionHdrID
					FROM CommissionDetFor CDF
					JOIN #TempOrder OH 
						ON (
							(OH.CategoryName = CDF.CategoryName AND OH.ItemNo = CDF.ItemNo) OR
							(OH.CategoryName = CDF.CategoryName AND ISNULL(OH.ItemNo, '') = '')
						)
					WHERE 
						CDF.CommissionHdrID = @CommissionHdrID
						AND OH.ItemType = 'POINT_SOLD' 
						AND OH.Sales2ndPerson IS NOT NULL
						
					INSERT INTO @TempDeductionAmount
					SELECT 
						OH.Sales2ndPerson, 
						OH.Quantity * @DeductionValue 
						,@CommissionHdrID
					FROM CommissionDetFor CDF
					JOIN #TempOrder OH 
						ON (
							(OH.CategoryName = CDF.CategoryName AND OH.ItemNo = CDF.ItemNo) OR
							(OH.CategoryName = CDF.CategoryName AND ISNULL(OH.ItemNo, '') = '')
						)
					WHERE 
						CDF.CommissionHdrID = @CommissionHdrID
						AND OH.ItemType = 'POINT_SOLD'
						AND OH.Sales2ndPerson IS NOT NULL
						AND OH.Sales2ndPersonGroupID = @SalesGroupID
				END
				ELSE
				BEGIN
					INSERT INTO @TempDeductionAmount
					SELECT
						OH.Sales
						,-OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'POINT_SOLD' 
					AND OH.Sales2ndPerson IS NOT NULL
					
					INSERT INTO @TempDeductionAmount
					SELECT
						OH.Sales2ndPerson
						,OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'POINT_SOLD' 
					AND OH.Sales2ndPerson IS NOT NULL
					AND OH.Sales2ndPersonGroupID = @SalesGroupID
				END
			END
			ELSE
			BEGIN
				SELECT
					@UserInt1 = OH.Sales2ndPersonGroupID
				FROM #TempOrder OH
				WHERE OH.ItemType = 'POINT_SOLD'
				AND OH.Sales2ndPerson IS NOT NULL
				AND OH.SalesGroupID = @SalesGroupID
				
				DECLARE db_cursor5 CURSOR LOCAL FOR
					SELECT 
						CommissionHdrID
						,SchemeName
						,IsProduct
						,ProductWeight
						,IsService
						,ServiceWeight
						,IsPointSold
						,PointSoldWeight
						,IsPackageSold
						,PackageSoldWeight
						,IsPointRedeem
						,PointRedeemWeight
						,IsPackageRedeem
						,PackageRedeemWeight
						,IsDeductionFor2ndSalesPerson
						,DeductionBy
						,DeductionValue
						,SalesGroupID
						,CommissionBy
					FROM CommissionHdr
					WHERE
						SalesGroupID = @UserInt1
	
				OPEN db_cursor5
				FETCH NEXT FROM db_cursor5 INTO 
					@CommissionHdrID2
					,@SchemeName2
					,@IsProduct2
					,@ProductWeight2
					,@IsService2
					,@ServiceWeight2
					,@IsPointSold2
					,@PointSoldWeight2
					,@IsPackageSold2
					,@PackageSoldWeight2
					,@IsPointRedeem2
					,@PointRedeemWeight2
					,@IsPackageRedeem2
					,@PackageRedeemWeight2
					,@IsDeductionFor2ndSalesPerson2
					,@DeductionBy2
					,@DeductionValue2
					,@SalesGroupID2
					,@CommissionBy2;
	
				WHILE @@FETCH_STATUS = 0
				BEGIN
					INSERT INTO @TempSales
					SELECT 
						OH.Sales2ndPerson
						,OH.ItemType
						,OH.CategoryName
						,OH.ItemNo
						,OH.ItemName
						,OH.Quantity
						,(OH.Amount * @ProductWeight2 / 100) * @DeductionValue / 100 as Amount
						,@CommissionHdrID2
						,OH.Sales2ndPersonGroupID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'POINT_SOLD'
					AND OH.Sales2ndPerson IS NOT NULL
					AND OH.SalesGroupID = @SalesGroupID
					AND @CommissionBy = 'Percentage'
					
					FETCH NEXT FROM db_cursor5 INTO 
						@CommissionHdrID2
						,@SchemeName2
						,@IsProduct2
						,@ProductWeight2
						,@IsService2
						,@ServiceWeight2
						,@IsPointSold2
						,@PointSoldWeight2
						,@IsPackageSold2
						,@PackageSoldWeight2
						,@IsPointRedeem2
						,@PointRedeemWeight2
						,@IsPackageRedeem2
						,@PackageRedeemWeight2
						,@IsDeductionFor2ndSalesPerson2
						,@DeductionBy2
						,@DeductionValue2
						,@SalesGroupID2
						,@CommissionBy2;
				END
				
				CLOSE db_cursor5
				
				DEALLOCATE db_cursor5
			END
		END
	END
	
	IF @IsPointRedeem = 1
	BEGIN
		INSERT INTO @TempSales
		SELECT 
			OH.Sales
			,OH.ItemType
			,OH.CategoryName
			,OH.ItemNo
			,OH.ItemName
			,OH.Quantity * @PointRedeemWeight / 100
			,CASE 
				WHEN @IsDeductionFor2ndSalesPerson = 1 AND OH.Sales2ndPerson IS NOT NULL AND @DeductionBy = 'Percentage' THEN (OH.Amount * @PointRedeemWeight / 100) * (100 - @DeductionValue) / 100
				ELSE (OH.Amount * @PointRedeemWeight / 100)
			END as Amount
			,@CommissionHdrID
			,OH.SalesGroupID
		FROM #TempOrder OH
		WHERE OH.ItemType = 'POINT_REDEEM'
		AND OH.SalesGroupID = @SalesGroupID;
		
		IF @IsDeductionFor2ndSalesPerson = 1
		BEGIN
			IF @DeductionBy = 'Amount'
			BEGIN
				SELECT @Count_CFD = (SELECT COUNT(*) FROM CommissionDetFor WHERE CommissionHdrID = @CommissionHdrID)
				IF @Count_CFD > 0
				BEGIN
					INSERT INTO @TempDeductionAmount
					SELECT 
						OH.Sales, 
						-OH.Quantity * @DeductionValue 
						,@CommissionHdrID
					FROM CommissionDetFor CDF
					JOIN #TempOrder OH 
						ON (
							(OH.CategoryName = CDF.CategoryName AND OH.ItemNo = CDF.ItemNo) OR
							(OH.CategoryName = CDF.CategoryName AND ISNULL(OH.ItemNo, '') = '')
						)
					WHERE 
						CDF.CommissionHdrID = @CommissionHdrID
						AND OH.ItemType = 'POINT_REDEEM' 
						AND OH.Sales2ndPerson IS NOT NULL
						
					INSERT INTO @TempDeductionAmount
					SELECT 
						OH.Sales2ndPerson, 
						OH.Quantity * @DeductionValue 
						,@CommissionHdrID
					FROM CommissionDetFor CDF
					JOIN #TempOrder OH 
						ON (
							(OH.CategoryName = CDF.CategoryName AND OH.ItemNo = CDF.ItemNo) OR
							(OH.CategoryName = CDF.CategoryName AND ISNULL(OH.ItemNo, '') = '')
						)
					WHERE 
						CDF.CommissionHdrID = @CommissionHdrID
						AND OH.ItemType = 'POINT_REDEEM'
						AND OH.Sales2ndPerson IS NOT NULL
						AND OH.Sales2ndPersonGroupID = @SalesGroupID
				END
				ELSE
				BEGIN
					INSERT INTO @TempDeductionAmount
					SELECT
						OH.Sales
						,-OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'POINT_REDEEM' 
					AND OH.Sales2ndPerson IS NOT NULL
					
					INSERT INTO @TempDeductionAmount
					SELECT
						OH.Sales2ndPerson
						,OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'POINT_REDEEM' 
					AND OH.Sales2ndPerson IS NOT NULL
					AND OH.Sales2ndPersonGroupID = @SalesGroupID
				END
			END
			ELSE
			BEGIN
				SELECT
					@UserInt1 = OH.Sales2ndPersonGroupID
				FROM #TempOrder OH
				WHERE OH.ItemType = 'POINT_REDEEM'
				AND OH.Sales2ndPerson IS NOT NULL
				AND OH.SalesGroupID = @SalesGroupID
				
				DECLARE db_cursor5 CURSOR LOCAL FOR
					SELECT 
						CommissionHdrID
						,SchemeName
						,IsProduct
						,ProductWeight
						,IsService
						,ServiceWeight
						,IsPointSold
						,PointSoldWeight
						,IsPackageSold
						,PackageSoldWeight
						,IsPointRedeem
						,PointRedeemWeight
						,IsPackageRedeem
						,PackageRedeemWeight
						,IsDeductionFor2ndSalesPerson
						,DeductionBy
						,DeductionValue
						,SalesGroupID
						,CommissionBy
					FROM CommissionHdr
					WHERE
						SalesGroupID = @UserInt1
	
				OPEN db_cursor5
				FETCH NEXT FROM db_cursor5 INTO 
					@CommissionHdrID2
					,@SchemeName2
					,@IsProduct2
					,@ProductWeight2
					,@IsService2
					,@ServiceWeight2
					,@IsPointSold2
					,@PointSoldWeight2
					,@IsPackageSold2
					,@PackageSoldWeight2
					,@IsPointRedeem2
					,@PointRedeemWeight2
					,@IsPackageRedeem2
					,@PackageRedeemWeight2
					,@IsDeductionFor2ndSalesPerson2
					,@DeductionBy2
					,@DeductionValue2
					,@SalesGroupID2
					,@CommissionBy2;
	
				WHILE @@FETCH_STATUS = 0
				BEGIN
					INSERT INTO @TempSales
					SELECT 
						OH.Sales2ndPerson
						,OH.ItemType
						,OH.CategoryName
						,OH.ItemNo
						,OH.ItemName
						,OH.Quantity
						,(OH.Amount * @ProductWeight2 / 100) * @DeductionValue / 100 as Amount
						,@CommissionHdrID2
						,OH.Sales2ndPersonGroupID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'POINT_REDEEM'
					AND OH.Sales2ndPerson IS NOT NULL
					AND OH.SalesGroupID = @SalesGroupID
					AND @CommissionBy = 'Percentage'
					
					FETCH NEXT FROM db_cursor5 INTO 
						@CommissionHdrID2
						,@SchemeName2
						,@IsProduct2
						,@ProductWeight2
						,@IsService2
						,@ServiceWeight2
						,@IsPointSold2
						,@PointSoldWeight2
						,@IsPackageSold2
						,@PackageSoldWeight2
						,@IsPointRedeem2
						,@PointRedeemWeight2
						,@IsPackageRedeem2
						,@PackageRedeemWeight2
						,@IsDeductionFor2ndSalesPerson2
						,@DeductionBy2
						,@DeductionValue2
						,@SalesGroupID2
						,@CommissionBy2;
				END
				
				CLOSE db_cursor5
				
				DEALLOCATE db_cursor5
			END
		END
	END
	
	IF @IsPackageSold = 1
	BEGIN
		INSERT INTO @TempSales
		SELECT 
			OH.Sales
			,OH.ItemType
			,OH.CategoryName
			,OH.ItemNo
			,OH.ItemName
			,OH.Quantity * @PackageSoldWeight / 100
			,CASE 
				WHEN @IsDeductionFor2ndSalesPerson = 1 AND OH.Sales2ndPerson IS NOT NULL AND @DeductionBy = 'Percentage' THEN (OH.Amount * @PackageSoldWeight / 100) * (100 - @DeductionValue) / 100
				ELSE (OH.Amount * @PackageSoldWeight / 100)
			END as Amount
			,@CommissionHdrID
			,OH.SalesGroupID
		FROM #TempOrder OH
		WHERE OH.ItemType = 'PACKAGE_SOLD'
		AND OH.SalesGroupID = @SalesGroupID;
		
		IF @IsDeductionFor2ndSalesPerson = 1
		BEGIN
			IF @DeductionBy = 'Amount'
			BEGIN
				SELECT @Count_CFD = (SELECT COUNT(*) FROM CommissionDetFor WHERE CommissionHdrID = @CommissionHdrID)
				IF @Count_CFD > 0
				BEGIN
					INSERT INTO @TempDeductionAmount
					SELECT 
						OH.Sales, 
						-OH.Quantity * @DeductionValue 
						,@CommissionHdrID
					FROM CommissionDetFor CDF
					JOIN #TempOrder OH 
						ON (
							(OH.CategoryName = CDF.CategoryName AND OH.ItemNo = CDF.ItemNo) OR
							(OH.CategoryName = CDF.CategoryName AND ISNULL(OH.ItemNo, '') = '')
						)
					WHERE 
						CDF.CommissionHdrID = @CommissionHdrID
						AND OH.ItemType = 'PACKAGE_SOLD' 
						AND OH.Sales2ndPerson IS NOT NULL
						
					INSERT INTO @TempDeductionAmount
					SELECT 
						OH.Sales2ndPerson, 
						OH.Quantity * @DeductionValue 
						,@CommissionHdrID
					FROM CommissionDetFor CDF
					JOIN #TempOrder OH 
						ON (
							(OH.CategoryName = CDF.CategoryName AND OH.ItemNo = CDF.ItemNo) OR
							(OH.CategoryName = CDF.CategoryName AND ISNULL(OH.ItemNo, '') = '')
						)
					WHERE 
						CDF.CommissionHdrID = @CommissionHdrID
						AND OH.ItemType = 'PACKAGE_SOLD'
						AND OH.Sales2ndPerson IS NOT NULL
						AND OH.Sales2ndPersonGroupID = @SalesGroupID
				END
				ELSE
				BEGIN
					INSERT INTO @TempDeductionAmount
					SELECT
						OH.Sales
						,-OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'PACKAGE_SOLD' 
					AND OH.Sales2ndPerson IS NOT NULL
					
					INSERT INTO @TempDeductionAmount
					SELECT
						OH.Sales2ndPerson
						,OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'PACKAGE_SOLD' 
					AND OH.Sales2ndPerson IS NOT NULL
					AND OH.Sales2ndPersonGroupID = @SalesGroupID
				END
			END
			ELSE
			BEGIN
				SELECT
					@UserInt1 = OH.Sales2ndPersonGroupID
				FROM #TempOrder OH
				WHERE OH.ItemType = 'PACKAGE_SOLD'
				AND OH.Sales2ndPerson IS NOT NULL
				AND OH.SalesGroupID = @SalesGroupID
				
				DECLARE db_cursor5 CURSOR LOCAL FOR
					SELECT 
						CommissionHdrID
						,SchemeName
						,IsProduct
						,ProductWeight
						,IsService
						,ServiceWeight
						,IsPointSold
						,PointSoldWeight
						,IsPackageSold
						,PackageSoldWeight
						,IsPointRedeem
						,PointRedeemWeight
						,IsPackageRedeem
						,PackageRedeemWeight
						,IsDeductionFor2ndSalesPerson
						,DeductionBy
						,DeductionValue
						,SalesGroupID
						,CommissionBy
					FROM CommissionHdr
					WHERE
						SalesGroupID = @UserInt1
	
				OPEN db_cursor5
				FETCH NEXT FROM db_cursor5 INTO 
					@CommissionHdrID2
					,@SchemeName2
					,@IsProduct2
					,@ProductWeight2
					,@IsService2
					,@ServiceWeight2
					,@IsPointSold2
					,@PointSoldWeight2
					,@IsPackageSold2
					,@PackageSoldWeight2
					,@IsPointRedeem2
					,@PointRedeemWeight2
					,@IsPackageRedeem2
					,@PackageRedeemWeight2
					,@IsDeductionFor2ndSalesPerson2
					,@DeductionBy2
					,@DeductionValue2
					,@SalesGroupID2
					,@CommissionBy2;
	
				WHILE @@FETCH_STATUS = 0
				BEGIN
					INSERT INTO @TempSales
					SELECT 
						OH.Sales2ndPerson
						,OH.ItemType
						,OH.CategoryName
						,OH.ItemNo
						,OH.ItemName
						,OH.Quantity
						,(OH.Amount * @ProductWeight2 / 100) * @DeductionValue / 100 as Amount
						,@CommissionHdrID2
						,OH.Sales2ndPersonGroupID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'PACKAGE_SOLD'
					AND OH.Sales2ndPerson IS NOT NULL
					AND OH.SalesGroupID = @SalesGroupID
					AND @CommissionBy = 'Percentage'
					
					FETCH NEXT FROM db_cursor5 INTO 
						@CommissionHdrID2
						,@SchemeName2
						,@IsProduct2
						,@ProductWeight2
						,@IsService2
						,@ServiceWeight2
						,@IsPointSold2
						,@PointSoldWeight2
						,@IsPackageSold2
						,@PackageSoldWeight2
						,@IsPointRedeem2
						,@PointRedeemWeight2
						,@IsPackageRedeem2
						,@PackageRedeemWeight2
						,@IsDeductionFor2ndSalesPerson2
						,@DeductionBy2
						,@DeductionValue2
						,@SalesGroupID2
						,@CommissionBy2;
				END
				
				CLOSE db_cursor5
				
				DEALLOCATE db_cursor5
			END
		END
	END
	
	IF @IsPackageRedeem = 1
	BEGIN
		INSERT INTO @TempSales
		SELECT 
			OH.Sales
			,OH.ItemType
			,OH.CategoryName
			,OH.ItemNo
			,OH.ItemName
			,OH.Quantity * @PackageRedeemWeight / 100
			,CASE 
				WHEN @IsDeductionFor2ndSalesPerson = 1 AND OH.Sales2ndPerson IS NOT NULL AND @DeductionBy = 'Percentage' THEN (OH.Amount * @PackageRedeemWeight / 100) * (100 - @DeductionValue) / 100
				ELSE (OH.Amount * @PackageRedeemWeight / 100)
			END as Amount
			,@CommissionHdrID
			,OH.SalesGroupID
		FROM #TempOrder OH
		WHERE OH.ItemType = 'PACKAGE_REDEEM' AND OH.SalesGroupID = @SalesGroupID;
		
		IF @IsDeductionFor2ndSalesPerson = 1
		BEGIN
			IF @DeductionBy = 'Amount'
			BEGIN
				SELECT @Count_CFD = (SELECT COUNT(*) FROM CommissionDetFor WHERE CommissionHdrID = @CommissionHdrID)
				IF @Count_CFD > 0
				BEGIN
					INSERT INTO @TempDeductionAmount
					SELECT 
						OH.Sales, 
						-OH.Quantity * @DeductionValue
						,@CommissionHdrID 
					FROM CommissionDetFor CDF
					JOIN #TempOrder OH 
						ON (
							(OH.CategoryName = CDF.CategoryName AND OH.ItemNo = CDF.ItemNo) OR
							(OH.CategoryName = CDF.CategoryName AND ISNULL(OH.ItemNo, '') = '')
						)
					WHERE 
						CDF.CommissionHdrID = @CommissionHdrID
						AND OH.ItemType = 'PACKAGE_REDEEM' 
						AND OH.Sales2ndPerson IS NOT NULL
						
					INSERT INTO @TempDeductionAmount
					SELECT 
						OH.Sales2ndPerson, 
						OH.Quantity * @DeductionValue 
						,@CommissionHdrID
					FROM CommissionDetFor CDF
					JOIN #TempOrder OH 
						ON (
							(OH.CategoryName = CDF.CategoryName AND OH.ItemNo = CDF.ItemNo) OR
							(OH.CategoryName = CDF.CategoryName AND ISNULL(OH.ItemNo, '') = '')
						)
					WHERE 
						CDF.CommissionHdrID = @CommissionHdrID
						AND OH.ItemType = 'PACKAGE_REDEEM'
						AND OH.Sales2ndPerson IS NOT NULL
						AND OH.Sales2ndPersonGroupID = @SalesGroupID
				END
				ELSE
				BEGIN
					INSERT INTO @TempDeductionAmount
					SELECT
						OH.Sales
						,-OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'PACKAGE_REDEEM' 
					AND OH.Sales2ndPerson IS NOT NULL
					
					INSERT INTO @TempDeductionAmount
					SELECT
						OH.Sales2ndPerson
						,OH.Quantity * @DeductionValue
						,@CommissionHdrID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'PACKAGE_REDEEM' 
					AND OH.Sales2ndPerson IS NOT NULL
					AND OH.Sales2ndPersonGroupID = @SalesGroupID
				END
			END
			ELSE
			BEGIN
				SELECT
					@UserInt1 = OH.Sales2ndPersonGroupID
				FROM #TempOrder OH
				WHERE OH.ItemType = 'PACKAGE_REDEEM'
				AND OH.Sales2ndPerson IS NOT NULL
				AND OH.SalesGroupID = @SalesGroupID
				
				DECLARE db_cursor5 CURSOR LOCAL FOR
					SELECT 
						CommissionHdrID
						,SchemeName
						,IsProduct
						,ProductWeight
						,IsService
						,ServiceWeight
						,IsPointSold
						,PointSoldWeight
						,IsPackageSold
						,PackageSoldWeight
						,IsPointRedeem
						,PointRedeemWeight
						,IsPackageRedeem
						,PackageRedeemWeight
						,IsDeductionFor2ndSalesPerson
						,DeductionBy
						,DeductionValue
						,SalesGroupID
						,CommissionBy
					FROM CommissionHdr
					WHERE
						SalesGroupID = @UserInt1
	
				OPEN db_cursor5
				FETCH NEXT FROM db_cursor5 INTO 
					@CommissionHdrID2
					,@SchemeName2
					,@IsProduct2
					,@ProductWeight2
					,@IsService2
					,@ServiceWeight2
					,@IsPointSold2
					,@PointSoldWeight2
					,@IsPackageSold2
					,@PackageSoldWeight2
					,@IsPointRedeem2
					,@PointRedeemWeight2
					,@IsPackageRedeem2
					,@PackageRedeemWeight2
					,@IsDeductionFor2ndSalesPerson2
					,@DeductionBy2
					,@DeductionValue2
					,@SalesGroupID2
					,@CommissionBy2;
	
				WHILE @@FETCH_STATUS = 0
				BEGIN
					INSERT INTO @TempSales
					SELECT 
						OH.Sales2ndPerson
						,OH.ItemType
						,OH.CategoryName
						,OH.ItemNo
						,OH.ItemName
						,OH.Quantity
						,(OH.Amount * @ProductWeight2 / 100) * @DeductionValue / 100 as Amount
						,@CommissionHdrID2
						,OH.Sales2ndPersonGroupID
					FROM #TempOrder OH
					WHERE OH.ItemType = 'PACKAGE_REDEEM'
					AND OH.Sales2ndPerson IS NOT NULL
					AND OH.SalesGroupID = @SalesGroupID
					AND @CommissionBy = 'Percentage'
					
					FETCH NEXT FROM db_cursor5 INTO 
						@CommissionHdrID2
						,@SchemeName2
						,@IsProduct2
						,@ProductWeight2
						,@IsService2
						,@ServiceWeight2
						,@IsPointSold2
						,@PointSoldWeight2
						,@IsPackageSold2
						,@PackageSoldWeight2
						,@IsPointRedeem2
						,@PointRedeemWeight2
						,@IsPackageRedeem2
						,@PackageRedeemWeight2
						,@IsDeductionFor2ndSalesPerson2
						,@DeductionBy2
						,@DeductionValue2
						,@SalesGroupID2
						,@CommissionBy2;
				END
				
				CLOSE db_cursor5
				
				DEALLOCATE db_cursor5
			END
		END
	END
	FETCH NEXT FROM db_cursor INTO 
		@CommissionHdrID
		,@SchemeName
		,@IsProduct
		,@ProductWeight
		,@IsService
		,@ServiceWeight
		,@IsPointSold
		,@PointSoldWeight
		,@IsPackageSold
		,@PackageSoldWeight
		,@IsPointRedeem
		,@PointRedeemWeight
		,@IsPackageRedeem
		,@PackageRedeemWeight
		,@IsDeductionFor2ndSalesPerson
		,@DeductionBy
		,@DeductionValue
		,@SalesGroupID
		,@CommissionBy;
END
CLOSE db_cursor
--SELECT * FROM @TempDeductionAmount
--RETURN
-- debug Sales
--SELECT * FROM @TempSales;
DECLARE db_cursor2 CURSOR LOCAL FOR
	SELECT 
		CommissionHdrID
		,SchemeName
		,IsProduct
		,ProductWeight
		,IsService
		,ServiceWeight
		,IsPointSold
		,PointSoldWeight
		,IsPackageSold
		,PackageSoldWeight
		,IsPointRedeem
		,PointRedeemWeight
		,IsPackageRedeem
		,PackageRedeemWeight
		,IsDeductionFor2ndSalesPerson
		,DeductionBy
		,DeductionValue
		,SalesGroupID
		,CommissionBy
	FROM CommissionHdr
	--WHERE ISNULL(Userflag1,0) = 1
			
OPEN db_cursor2
FETCH NEXT FROM db_cursor2 INTO 
	@CommissionHdrID
	,@SchemeName
	,@IsProduct
	,@ProductWeight
	,@IsService
	,@ServiceWeight
	,@IsPointSold
	,@PointSoldWeight
	,@IsPackageSold
	,@PackageSoldWeight
	,@IsPointRedeem
	,@PointRedeemWeight
	,@IsPackageRedeem
	,@PackageRedeemWeight
	,@IsDeductionFor2ndSalesPerson
	,@DeductionBy
	,@DeductionValue
	,@SalesGroupID
	,@CommissionBy;
	
WHILE @@FETCH_STATUS = 0
BEGIN
	-- debug
	--SELECT @CommissionHdrID, @SchemeName
	
	SELECT 
		@CountFor = COUNT(*)
	FROM CommissionDetFor CDF WHERE CDF.CommissionHdrID = @CommissionHdrID;
	
	SELECT @UserFld1 = NULL, @UserFld2 = NULL, @UserFloat1 = NULL, @UserFloat2 = NULL;
	IF @CountFor > 0
	BEGIN
		IF @Generate = 1
		BEGIN			
			DECLARE db_cursor7 CURSOR LOCAL FOR
				SELECT
					Sales
					, TS.CommissionHdrID
					, @SchemeName as SchemeName
					, (CASE
						WHEN TS.ItemType = 'PRODUCT' THEN TS.ItemType + ' ' + CONVERT(VARCHAR, CONVERT(DECIMAL(18,0), @ProductWeight)) + '%'
						WHEN TS.ItemType = 'SERVICE' THEN TS.ItemType + ' ' + CONVERT(VARCHAR, CONVERT(DECIMAL(18,0), @ServiceWeight)) + '%'
						WHEN TS.ItemType = 'POINT_SOLD' THEN TS.ItemType + ' ' + CONVERT(VARCHAR, CONVERT(DECIMAL(18,0), @PointSoldWeight)) + '%'
						WHEN TS.ItemType = 'POINT_REDEEM' THEN TS.ItemType + ' ' + CONVERT(VARCHAR, CONVERT(DECIMAL(18,0), @PointRedeemWeight)) + '%'
						WHEN TS.ItemType = 'PACKAGE_SOLD' THEN TS.ItemType + ' ' + CONVERT(VARCHAR, CONVERT(DECIMAL(18,0), @PackageSoldWeight)) + '%'
						WHEN TS.ItemType = 'PACKAGE_REDEEM' THEN TS.ItemType + ' ' + CONVERT(VARCHAR, CONVERT(DECIMAL(18,0), @PackageRedeemWeight)) + '%'
						END
					) AS CommissionType
					, SUM(TS.SalesTotalAmount) as SalesTotalAmount
					, SUM(TS.SalesTotalQuantity) as SalesTotalQuantity
				FROM @TempSales TS
				LEFT JOIN CommissionDetFor CDF ON CDF.CommissionHdrID = TS.CommissionHdrID
				WHERE 
					TS.CommissionHdrID = @CommissionHdrID
					AND ((CDF.CategoryName = TS.Category AND CDF.ItemNo IS NULL) OR (CDF.CategoryName = TS.Category AND CDF.ItemNo = TS.ItemNo))
					AND (@FilterUserName = '' OR @FilterUserName = 'ALL' OR TS.Sales = @FilterUserName)
				GROUP BY Sales, TS.CommissionHdrID, TS.ItemType
			
			OPEN db_cursor7
			
			FETCH NEXT FROM db_cursor7 INTO
				@UserFld1
				,@UserInt1
				,@UserFld3
				,@UserFld4
				,@UserFloat4
				,@UserFloat5
			
			WHILE @@FETCH_STATUS = 0
			BEGIN
				DELETE FROM SalesCommissionDetails WHERE [Month] = @Month AND Staff = @UserFld1 AND CommissionType = @UserFld3 + ' - ' + @UserFld4;
				
				INSERT INTO SalesCommissionDetails ([Month], MonthDate, Staff, CommissionType, TotalSales, TotalQty)
				SELECT
					@Month
					,@Month
					,@UserFld1
					,@UserFld3 + ' - ' + @UserFld4
					,@UserFloat4
					,@UserFloat5
			
				FETCH NEXT FROM db_cursor7 INTO
					@UserFld1
					,@UserInt1
					,@UserFld3
					,@UserFld4
					,@UserFloat4
					,@UserFloat5
			END
			
			CLOSE db_cursor7
			
			DEALLOCATE db_cursor7
		END
	
		INSERT INTO @TempResultP1
		SELECT
			TS.Sales
			, TS.CommissionHdrID
			, @SchemeName
			, SUM(TS.SalesTotalAmount)
			, SUM(TS.SalesTotalQuantity)
		FROM @TempSales TS
		LEFT JOIN CommissionDetFor CDF ON CDF.CommissionHdrID = TS.CommissionHdrID
		WHERE
			--SalesGroupID = @SalesGroupID
			--AND 
			((CDF.CategoryName = TS.Category AND CDF.ItemNo IS NULL) OR (CDF.CategoryName = TS.Category AND CDF.ItemNo = TS.ItemNo))
			AND (@FilterUserName = '' OR @FilterUserName = 'ALL' OR TS.Sales = @FilterUserName)
		GROUP BY Sales, TS.CommissionHdrID
	END
	ELSE
	BEGIN
		IF @Generate = 1
		BEGIN			
			DECLARE db_cursor7 CURSOR LOCAL FOR
				SELECT
					Sales
					, TS.CommissionHdrID
					, @SchemeName as SchemeName
					, (CASE
						WHEN TS.ItemType = 'PRODUCT' THEN TS.ItemType + ' ' + CONVERT(VARCHAR, CONVERT(DECIMAL(18,0), @ProductWeight)) + '%'
						WHEN TS.ItemType = 'SERVICE' THEN TS.ItemType + ' ' + CONVERT(VARCHAR, CONVERT(DECIMAL(18,0), @ServiceWeight)) + '%'
						WHEN TS.ItemType = 'POINT_SOLD' THEN TS.ItemType + ' ' + CONVERT(VARCHAR, CONVERT(DECIMAL(18,0), @PointSoldWeight)) + '%'
						WHEN TS.ItemType = 'POINT_REDEEM' THEN TS.ItemType + ' ' + CONVERT(VARCHAR, CONVERT(DECIMAL(18,0), @PointRedeemWeight)) + '%'
						WHEN TS.ItemType = 'PACKAGE_SOLD' THEN TS.ItemType + ' ' + CONVERT(VARCHAR, CONVERT(DECIMAL(18,0), @PackageSoldWeight)) + '%'
						WHEN TS.ItemType = 'PACKAGE_REDEEM' THEN TS.ItemType + ' ' + CONVERT(VARCHAR, CONVERT(DECIMAL(18,0), @PackageRedeemWeight)) + '%'
						END
					) AS CommissionType
					, SUM(TS.SalesTotalAmount) as SalesTotalAmount
					, SUM(TS.SalesTotalQuantity) as SalesTotalQuantity
				FROM @TempSales TS
				WHERE
					TS.CommissionHdrID = @CommissionHdrID
					AND (@FilterUserName = '' OR @FilterUserName = 'ALL' OR TS.Sales = @FilterUserName)
				GROUP BY Sales, TS.CommissionHdrID, TS.ItemType
			
			OPEN db_cursor7
			
			FETCH NEXT FROM db_cursor7 INTO
				@UserFld1
				,@UserInt1
				,@UserFld3
				,@UserFld4
				,@UserFloat4
				,@UserFloat5
			
			WHILE @@FETCH_STATUS = 0
			BEGIN
				DELETE FROM SalesCommissionDetails WHERE [Month] = @Month AND Staff = @UserFld1 AND CommissionType = @UserFld3 + ' - ' + @UserFld4;
				
				INSERT INTO SalesCommissionDetails ([Month], MonthDate, Staff, CommissionType, TotalSales, TotalQty)
				SELECT
					@Month
					,@Month
					,@UserFld1
					,@UserFld3 + ' - ' + @UserFld4
					,@UserFloat4
					,@UserFloat5
			
				FETCH NEXT FROM db_cursor7 INTO
					@UserFld1
					,@UserInt1
					,@UserFld3
					,@UserFld4
					,@UserFloat4
					,@UserFloat5
			END
			
			CLOSE db_cursor7
			
			DEALLOCATE db_cursor7
		END
		INSERT INTO @TempResultP1
		SELECT
			Sales
			, TS.CommissionHdrID
			, @SchemeName
			, SUM(TS.SalesTotalAmount)
			, SUM(TS.SalesTotalQuantity)
		FROM @TempSales TS
		WHERE
			--TS.SalesGroupID = @SalesGroupID
			--AND 
			TS.CommissionHdrID = @CommissionHdrID
			AND (@FilterUserName = '' OR @FilterUserName = 'ALL' OR TS.Sales = @FilterUserName)
		GROUP BY Sales, TS.CommissionHdrID
	END
	FETCH NEXT FROM db_cursor2 INTO 
		@CommissionHdrID
		,@SchemeName
		,@IsProduct
		,@ProductWeight
		,@IsService
		,@ServiceWeight
		,@IsPointSold
		,@PointSoldWeight
		,@IsPackageSold
		,@PackageSoldWeight
		,@IsPointRedeem
		,@PointRedeemWeight
		,@IsPackageRedeem
		,@PackageRedeemWeight
		,@IsDeductionFor2ndSalesPerson
		,@DeductionBy
		,@DeductionValue
		,@SalesGroupID
		,@CommissionBy;
END
CLOSE db_cursor2
---- debug
--SELECT * FROM @TempResultP1
--SELECT @CommissionBasedOn
DECLARE db_cursor3 CURSOR LOCAL FOR
	SELECT 
		TR.Sales
		,TR.CommissionHdrID
		,TR.SchemeName
		,TR.TotalAmount
		,TR.TotalQuantity
	FROM @TempResultP1 TR
OPEN db_cursor3
FETCH NEXT FROM db_cursor3 INTO 
	@UserFld1
	,@UserInt1
	,@UserFld2
	,@UserFloat1
	,@UserFloat2
WHILE @@FETCH_STATUS = 0
BEGIN
	--SELECT @UserFld1, @UserInt1, @UserFld2, @UserFloat1, @UserFloat2
	
	IF @CommissionBasedOn = 'Total'
		BEGIN
			IF @CommissionBy = 'Percentage'
			BEGIN
				INSERT INTO @TempResultP2
				SELECT
					@UserFld1
					,@UserFld2
					,@UserFloat1
					,@UserFloat2
					,@UserFloat1 * CDB.Value / 100
				FROM CommissionDetBy CDB
				WHERE CDB.CommissionHdrID = @UserInt1 
				AND @UserFloat1 >= CDB.[From] AND @UserFloat1 <= CDB.[To]
				ORDER BY CDB.[From] ASC, CDB.[To] ASC, CDB.Value ASC
				
				IF @Generate = 1
				BEGIN
					DELETE FROM SalesCommissionDetails_Commission WHERE Month = @Month AND Staff = @UserFld1 AND Scheme = @UserFld2
					
					INSERT INTO SalesCommissionDetails_Commission
					SELECT
						@Month
						,@UserFld1
						,@UserFld2
						,CAST(CDB.[From] as VARCHAR(20)) + '-' + CAST(CDB.[To] as VARCHAR(20))
						,@UserFloat1 * CDB.Value / 100
					FROM CommissionDetBy CDB
					WHERE CDB.CommissionHdrID = @UserInt1 
					AND @UserFloat1 >= CDB.[From] AND @UserFloat1 <= CDB.[To]
					ORDER BY CDB.[From] ASC, CDB.[To] ASC, CDB.Value ASC
				END
			END
			ELSE IF @CommissionBy = 'Quantity'		
			BEGIN
				INSERT INTO @TempResultP2
				SELECT
					@UserFld1
					,@UserFld2
					,@UserFloat1
					,@UserFloat2
					,CDB.Value
				FROM CommissionDetBy CDB
				WHERE CDB.CommissionHdrID = @UserInt1 
				AND @UserFloat2 >= CDB.[From] AND @UserFloat2 <= CDB.[To]
				ORDER BY CDB.[From] ASC, CDB.[To] ASC, CDB.Value ASC
				
				IF @Generate = 1
				BEGIN
					DELETE FROM SalesCommissionDetails_Commission WHERE Month = @Month AND Staff = @UserFld1 AND Scheme = @UserFld2
					
					INSERT INTO SalesCommissionDetails_Commission
					SELECT
						@Month
						,@UserFld1
						,@UserFld2
						,CAST(CDB.[From] as VARCHAR(20)) + '-' + CAST(CDB.[To] as VARCHAR(20))
						,@UserFloat1 * CDB.Value / 100
					FROM CommissionDetBy CDB
					WHERE CDB.CommissionHdrID = @UserInt1 
					AND @UserFloat1 >= CDB.[From] AND @UserFloat1 <= CDB.[To]
					ORDER BY CDB.[From] ASC, CDB.[To] ASC, CDB.Value ASC
				END
			END
		END
		ELSE IF @CommissionBasedOn = 'Bracket'
		BEGIN
			SELECT @UserFloat3 = 0
			
			DECLARE db_cursor4 CURSOR LOCAL FOR
				SELECT 
					CDB.[From]
					,CDB.[To]
					,CDB.[Value]
				FROM CommissionDetBy CDB
				WHERE CDB.CommissionHdrID = @UserInt1
				ORDER BY CDB.[From] ASC, CDB.[To] ASC, CDB.Value ASC
			
			OPEN db_cursor4
			FETCH NEXT FROM db_cursor4 INTO 
				@From
				,@To
				,@Value
		
			WHILE @@FETCH_STATUS = 0
			BEGIN
				
				IF @CommissionBy = 'Percentage'
				BEGIN
					IF @UserFloat1 >= @From
					BEGIN
						IF @UserFloat1 >= @To
							SELECT @UserFloat3 = @UserFloat3 + ((@To - @From + 1) * @Value / 100)
						ELSE
							SELECT @UserFloat3 = @UserFloat3 + ((@UserFloat1 - @From + 1) * @Value / 100)
					END
				END
				ELSE IF @CommissionBy = 'Quantity'
				BEGIN
					IF @UserFloat2 >= @From
						SELECT @UserFloat3 = @UserFloat3 + @Value
				END
				
				FETCH NEXT FROM db_cursor4 INTO 
					@From
					,@To
					,@Value
			END
			
			CLOSE db_cursor4
			
			DEALLOCATE db_cursor4
			
			IF @UserFld1 IS NOT NULL
			BEGIN
				INSERT INTO @TempResultP2
				SELECT
					@UserFld1
					,@UserFld2
					,@UserFloat1
					,@UserFloat2
					,@UserFloat3;
					
				IF @Generate = 1
				BEGIN
					DELETE FROM SalesCommissionDetails_Commission WHERE Month = @Month AND Staff = @UserFld1 AND Scheme = @UserFld2
					
					INSERT INTO SalesCommissionDetails_Commission
					SELECT
						@Month
						,@UserFld1
						,@UserFld2
						,''
						,@UserFloat3
					FROM CommissionDetBy CDB
					WHERE CDB.CommissionHdrID = @UserInt1 
					AND @UserFloat1 >= CDB.[From] AND @UserFloat1 <= CDB.[To]
					ORDER BY CDB.[From] ASC, CDB.[To] ASC, CDB.Value ASC
				END
			END
		END
	FETCH NEXT FROM db_cursor3 INTO 
		@UserFld1
		,@UserInt1
		,@UserFld2
		,@UserFloat1
		,@UserFloat2
END
		
CLOSE db_cursor3
DEALLOCATE db_cursor3
-- debug
--SELECT * FROM @TempResultP2
--SELECT * FROM @TempResultP1
--SELECT * FROM @TempDeductionAmount;
IF @Generate = 1
BEGIN
	DECLARE db_cursor6 CURSOR LOCAL FOR
		SELECT 
			Sales
			, SUM(Amount) as TotalDeduction
		FROM @TempDeductionAmount TDA
		GROUP BY Sales
	OPEN db_cursor6
	FETCH NEXT FROM db_cursor6 INTO 
		@UserFld1
		,@UserFloat1
	WHILE @@FETCH_STATUS = 0
	BEGIN
		DELETE FROM SalesCommissionDetails_Deduction WHERE Staff = @UserFld1 AND [Month] = @Month
		
		INSERT INTO SalesCommissionDetails_Deduction
		SELECT
			@Month
			,@UserFld1
			,@UserFloat1
		FETCH NEXT FROM db_cursor6 INTO 
		@UserFld1
		,@UserFloat1
	END
	CLOSE db_cursor6
END
--SELECT * FROM @TempDeductionAmount;
INSERT INTO @TempResultP2
SELECT
	TDA.Sales
	,'No Scheme'
	,0
	,0
	,0 --SUM(TDA.Amount)
FROM @TempDeductionAmount TDA
LEFT JOIN @TempResultP2 TR
	ON TR.Sales = TDA.Sales
WHERE
	TR.Sales IS NULL
GROUP BY TDA.Sales
--SELECT 
--	Sales
--	,SUM(Amount) as Amount
--FROM @TempDeductionAmount
--GROUP BY Sales
--SELECT * FROM @TempResultP2
--SELECT
--	TR.Sales
--	,TR.SchemeName
--	,TR.TotalQuantity
--	,TR.TotalAmount
--	,TR.TotalCommission + ISNULL(TDA.Amount, 0) as TotalCommission
--FROM @TempResultP2 TR
--LEFT JOIN (
--	SELECT 
--		Sales
--		,SUM(Amount) as Amount
--	FROM @TempDeductionAmount
--	GROUP BY Sales
--)TDA
--	ON TDA.Sales = TR.Sales
--WHERE (@FilterUserName = '' OR @FilterUserName = 'ALL' OR TR.Sales = @FilterUserName)
SELECT * FROM (
SELECT
	TR.Sales
	,TR.SchemeName
	,TR.TotalQuantity
	,TR.TotalAmount
	,TR.TotalCommission as TotalCommission
FROM @TempResultP2 TR
UNION ALL
SELECT
	Sales
	,'Deduction'
	,0
	,0
	,SUM(Amount)
FROM @TempDeductionAmount
GROUP BY Sales
) TMP
ORDER BY Sales
END
;

